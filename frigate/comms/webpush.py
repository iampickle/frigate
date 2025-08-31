"""Handle sending notifications for Frigate via Firebase."""

import datetime
import json
import logging
import os
import queue
import threading
from dataclasses import dataclass
from multiprocessing.synchronize import Event as MpEvent
from typing import Any, Callable

from py_vapid import Vapid01
from pywebpush import WebPusher
from titlecase import titlecase

from frigate.comms.base_communicator import Communicator
from frigate.comms.config_updater import ConfigSubscriber
from frigate.config import FrigateConfig
from frigate.const import CONFIG_DIR
from frigate.models import User

logger = logging.getLogger(__name__)


@dataclass
class PushNotification:
    user: str
    payload: dict[str, Any]
    title: str
    message: str
    direct_url: str = ""
    image: str = ""
    notification_type: str = "alert"
    ttl: int = 0


class WebPushClient(Communicator):  # type: ignore[misc]
    """Frigate wrapper for webpush client."""

    def __init__(self, config: FrigateConfig, stop_event: MpEvent) -> None:
        self.config = config
        self.stop_event = stop_event
        self.claim_headers: dict[str, dict[str, str]] = {}
        self.refresh: int = 0
        self.web_pushers: dict[str, list[WebPusher]] = {}
        self.expired_subs: dict[str, list[str]] = {}
        self.suspended_cameras: dict[str, int] = {
            c.name: 0 for c in self.config.cameras.values()
        }
        self.last_camera_notification_time: dict[str, float] = {
            c.name: 0 for c in self.config.cameras.values()
        }
        self.last_notification_time: float = 0
        # Gewicht-Queues pro Kamera und Stunde: {camera: {hour: [timestamps]}}
        # Jeder Timestamp repräsentiert eine Benachrichtigung
        self.weights_file = os.path.join(CONFIG_DIR, "notification_weights.json")
        self.camera_weight_queues: dict[str, dict[int, list[float]]] = self._load_weights()
        self.last_weights_save_time: float = 0
        self.weights_save_interval: float = 30.0  # Speichere nur alle 30 Sekunden
        self.pending_weight_changes: bool = False
        self.notification_queue: queue.Queue[PushNotification] = queue.Queue()
        self.notification_thread = threading.Thread(
            target=self._process_notifications, daemon=True
        )
        self.notification_thread.start()

        if not self.config.notifications.email:
            logger.warning("Email must be provided for push notifications to be sent.")

        # Pull keys from PEM or generate if they do not exist
        self.vapid = Vapid01.from_file(os.path.join(CONFIG_DIR, "notifications.pem"))

        users: list[User] = (
            User.select(User.username, User.notification_tokens).dicts().iterator()
        )
        for user in users:
            self.web_pushers[user["username"]] = []
            for sub in user["notification_tokens"]:
                self.web_pushers[user["username"]].append(WebPusher(sub))

        # notification config updater
        self.config_subscriber = ConfigSubscriber("config/notifications")

    def subscribe(self, receiver: Callable) -> None:
        """Wrapper for allowing dispatcher to subscribe."""
        pass

    def check_registrations(self) -> None:
        # check for valid claim or create new one
        now = datetime.datetime.now().timestamp()
        if len(self.claim_headers) == 0 or self.refresh < now:
            self.refresh = int(
                (datetime.datetime.now() + datetime.timedelta(hours=1)).timestamp()
            )
            endpoints: set[str] = set()

            # get a unique set of push endpoints
            for pushers in self.web_pushers.values():
                for push in pushers:
                    endpoint: str = push.subscription_info["endpoint"]
                    endpoints.add(endpoint[0 : endpoint.index("/", 10)])

            # create new claim
            for endpoint in endpoints:
                claim = {
                    "sub": f"mailto:{self.config.notifications.email}",
                    "aud": endpoint,
                    "exp": self.refresh,
                }
                self.claim_headers[endpoint] = self.vapid.sign(claim)

    def cleanup_registrations(self) -> None:
        # delete any expired subs
        if len(self.expired_subs) > 0:
            for user, expired in self.expired_subs.items():
                user_subs = []

                # get all subscriptions, removing ones that are expired
                stored_user: User = User.get_by_id(user)
                for token in stored_user.notification_tokens:
                    if token["endpoint"] in expired:
                        continue

                    user_subs.append(token)

                # overwrite the database and reset web pushers
                User.update(notification_tokens=user_subs).where(
                    User.username == user
                ).execute()

                self.web_pushers[user] = []

                for sub in user_subs:
                    self.web_pushers[user].append(WebPusher(sub))

                logger.info(
                    f"Cleaned up {len(expired)} notification subscriptions for {user}"
                )

        self.expired_subs = {}

    def _load_weights(self) -> dict[str, dict[int, list[float]]]:
        """Lädt gespeicherte Gewichte von der Festplatte."""
        try:
            if os.path.exists(self.weights_file):
                with open(self.weights_file, 'r') as f:
                    saved_weights = json.load(f)
                    
                # Erstelle eine neue Struktur mit den aktuellen Kameras
                weights = {}
                for camera_name, camera in self.config.cameras.items():
                    time_slots = camera.notifications.weight_time_slots
                    if camera_name in saved_weights:
                        # Lade gespeicherte Gewichte, aber nur für gültige Stunden
                        weights[camera_name] = {}
                        for hour in range(time_slots):
                            hour_str = str(hour)
                            if hour_str in saved_weights[camera_name]:
                                weights[camera_name][hour] = saved_weights[camera_name][hour_str]
                            else:
                                weights[camera_name][hour] = []
                    else:
                        # Neue Kamera, initialisiere leere Gewichte
                        weights[camera_name] = {h: [] for h in range(time_slots)}
                        
                logger.info(f"Gewichtsdaten geladen für {len(weights)} Kameras")
                return weights
        except Exception as e:
            logger.warning(f"Fehler beim Laden der Gewichtsdaten: {e}")
            
        # Fallback: erstelle neue leere Struktur
        return {
            c.name: {h: [] for h in range(c.notifications.weight_time_slots)}
            for c in self.config.cameras.values()
        }

    def _save_weights(self, force: bool = False) -> None:
        """Speichert die aktuellen Gewichte auf die Festplatte mit Batch-Optimierung."""
        current_time = datetime.datetime.now().timestamp()
        
        # Speichere nur wenn erzwungen oder genug Zeit vergangen ist und Änderungen vorliegen
        if not force and (
            not self.pending_weight_changes or 
            current_time - self.last_weights_save_time < self.weights_save_interval
        ):
            return
            
        try:
            # Konvertiere int keys zu strings für JSON serialization
            serializable_weights = {}
            for camera, hours in self.camera_weight_queues.items():
                serializable_weights[camera] = {str(hour): timestamps for hour, timestamps in hours.items()}
                
            with open(self.weights_file, 'w') as f:
                json.dump(serializable_weights, f, indent=2)
                
            self.last_weights_save_time = current_time
            self.pending_weight_changes = False
            logger.debug("Gewichtsdaten gespeichert")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Gewichtsdaten: {e}")

    def suspend_notifications(self, camera: str, minutes: int) -> None:
        """Suspend notifications for a specific camera."""
        suspend_until = int(
            (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).timestamp()
        )
        self.suspended_cameras[camera] = suspend_until
        logger.info(
            f"Notifications for {camera} suspended until {datetime.datetime.fromtimestamp(suspend_until).strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def unsuspend_notifications(self, camera: str) -> None:
        """Unsuspend notifications for a specific camera."""
        self.suspended_cameras[camera] = 0
        logger.info(f"Notifications for {camera} unsuspended")

    def is_camera_suspended(self, camera: str) -> bool:
        return datetime.datetime.now().timestamp() <= self.suspended_cameras[camera]

    def publish(self, topic: str, payload: Any, retain: bool = False) -> None:
        """Wrapper for publishing when client is in valid state."""
        # check for updated notification config
        _, updated_notification_config = self.config_subscriber.check_for_update()

        if updated_notification_config:
            self.config.notifications = updated_notification_config

        updates = self.config_subscriber.check_for_updates()

        if "add" in updates:
            for camera in updates["add"]:
                self.suspended_cameras[camera] = 0
                self.last_camera_notification_time[camera] = 0
                # Initialize weight queue tracking for new camera
                self.camera_weight_queues[camera] = {
                    h: [] for h in range(self.config.cameras[camera].notifications.weight_time_slots)
                }

        if topic == "reviews":
            decoded = json.loads(payload)
            camera = decoded["before"]["camera"]
            if not self.config.cameras[camera].notifications.enabled:
                return
            if self.is_camera_suspended(camera):
                logger.debug(f"Notifications for {camera} are currently suspended.")
                return
            self.send_alert(decoded)
        elif topic == "notification_test":
            if not self.config.notifications.enabled and not any(
                cam.notifications.enabled for cam in self.config.cameras.values()
            ):
                logger.debug(
                    "No cameras have notifications enabled, test notification not sent"
                )
                return
            self.send_notification_test()

    def send_push_notification(
        self,
        user: str,
        payload: dict[str, Any],
        title: str,
        message: str,
        direct_url: str = "",
        image: str = "",
        notification_type: str = "alert",
        ttl: int = 0,
    ) -> None:
        notification = PushNotification(
            user=user,
            payload=payload,
            title=title,
            message=message,
            direct_url=direct_url,
            image=image,
            notification_type=notification_type,
            ttl=ttl,
        )
        self.notification_queue.put(notification)

    def _process_notifications(self) -> None:
        while not self.stop_event.is_set():
            try:
                notification = self.notification_queue.get(timeout=1.0)
                self.check_registrations()

                for pusher in self.web_pushers[notification.user]:
                    endpoint = pusher.subscription_info["endpoint"]
                    headers = self.claim_headers[
                        endpoint[: endpoint.index("/", 10)]
                    ].copy()
                    headers["urgency"] = "high"

                    resp = pusher.send(
                        headers=headers,
                        ttl=notification.ttl,
                        data=json.dumps(
                            {
                                "title": notification.title,
                                "message": notification.message,
                                "direct_url": notification.direct_url,
                                "image": notification.image,
                                "id": notification.payload.get("after", {}).get(
                                    "id", ""
                                ),
                                "type": notification.notification_type,
                            }
                        ),
                        timeout=10,
                    )

                    if resp.status_code in (404, 410):
                        self.expired_subs.setdefault(notification.user, []).append(
                            endpoint
                        )
                        logger.debug(
                            f"Notification endpoint expired for {notification.user}, received {resp.status_code}"
                        )
                    elif resp.status_code != 201:
                        logger.warning(
                            f"Failed to send notification to {notification.user} :: {resp.status_code}"
                        )

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing notification: {str(e)}")

    def _get_dynamic_weight_factor(self, camera: str, base_weight_factor: float) -> float:
        """Berechnet einen dynamischen Gewichtsfaktor basierend auf verschiedenen Faktoren."""
        # Verwende UTC für konsistente Berechnungen, aber lokale Zeit für Tageszeit-Logik
        now = datetime.datetime.now()
        hour = now.hour
        weekday = now.weekday()  # 0=Montag, 6=Sonntag
        
        # Basis-Faktor
        dynamic_factor = base_weight_factor
        
        # 1. Tageszeit-Anpassung
        if 22 <= hour or hour <= 6:  # Nachtzeit (22:00 - 06:59)
            # Nachts weniger aggressiv (50% weniger)
            time_modifier = 0.5
        elif 7 <= hour <= 9 or 17 <= hour <= 21:  # Morgen/Abend (07:00-09:59, 17:00-21:59)
            # Morgens und abends normaler Faktor
            time_modifier = 1.0
        else:  # Tagsüber (10:00 - 16:59)
            # Tagsüber aggressiver (25% mehr)
            time_modifier = 1.25
        
        dynamic_factor *= time_modifier
        
        # 2. Wochentag-Anpassung
        if weekday >= 5:  # Wochenende (Samstag=5, Sonntag=6)
            # Am Wochenende weniger streng (20% weniger)
            weekday_modifier = 0.8
        else:  # Werktag
            weekday_modifier = 1.0
        
        dynamic_factor *= weekday_modifier
        
        # 3. Selbstregulierung: Berücksichtige die aktuelle Wirksamkeit des Gewichtssystems
        current_weight = self._get_normalized_weight_count(camera, hour)
        base_cooldown = self.config.cameras[camera].notifications.cooldown
        current_cooldown_multiplier = 1 + current_weight * base_weight_factor
        current_effective_cooldown = base_cooldown * min(current_cooldown_multiplier, self.config.cameras[camera].notifications.weight_max_factor)
        
        # Wenn der aktuelle Cooldown bereits hoch ist, reduziere den Faktor moderater
        # Konfigurierbare Schwellwerte für bessere Kontrolle
        self_regulation_threshold = 2.0  # Bei 2x base_cooldown beginnt Regulation
        self_regulation_strength = 0.3   # Stärke der Regulation (0.3 = moderate Reduktion)
        
        if current_effective_cooldown > base_cooldown * self_regulation_threshold:
            cooldown_ratio = current_effective_cooldown / base_cooldown
            # Sanftere Selbstregulierung - nicht so aggressiv wie vorher
            regulation_factor = 1.0 - (cooldown_ratio - self_regulation_threshold) * self_regulation_strength / 10
            self_regulation_modifier = max(0.2, regulation_factor)
        else:
            self_regulation_modifier = 1.0
        
        dynamic_factor *= self_regulation_modifier
        
        # 4. Gesamtaktivität der Kamera in den letzten Stunden (angepasst)
        total_recent_notifications = 0
        for h in range(max(0, hour-3), hour+1):  # Letzte 3-4 Stunden
            slot = h % self.config.cameras[camera].notifications.weight_time_slots
            total_recent_notifications += self._get_normalized_weight_count(camera, slot)
        
        # Berücksichtige auch hier die Selbstregulierung
        if total_recent_notifications > 10:
            activity_modifier = 1.5
        elif total_recent_notifications > 5:
            activity_modifier = 1.2
        elif total_recent_notifications <= 1:
            activity_modifier = 0.7
        else:
            activity_modifier = 1.0
        
        dynamic_factor *= activity_modifier
        
        # 5. Zeit seit letzter Notification für diese Kamera
        last_notification_age = now.timestamp() - self.last_camera_notification_time[camera]
        if last_notification_age < 300:  # Weniger als 5 Minuten
            recency_modifier = 1.3
        elif last_notification_age < 3600:  # Weniger als 1 Stunde
            recency_modifier = 1.1
        elif last_notification_age > 21600:  # Mehr als 6 Stunden
            recency_modifier = 0.6
        else:
            recency_modifier = 1.0
        
        dynamic_factor *= recency_modifier
        
        # Begrenze den finalen Faktor auf sinnvolle Werte
        # Mindestens 10% des ursprünglichen Faktors, höchstens 300%
        min_factor = base_weight_factor * 0.1
        max_factor = base_weight_factor * 3.0
        final_factor = max(min_factor, min(dynamic_factor, max_factor))
        
        # Log nur bei signifikanten Änderungen
        if abs(final_factor - base_weight_factor) > base_weight_factor * 0.2:
            logger.debug(
                f"Dynamic weight factor for {camera}: {base_weight_factor:.3f} -> {final_factor:.3f} "
                f"(time: {time_modifier:.2f}, weekday: {weekday_modifier:.2f}, self-reg: {self_regulation_modifier:.2f}, activity: {activity_modifier:.2f}, recency: {recency_modifier:.2f})"
            )
        
        return final_factor

    def _get_weighted_cooldown(self, camera: str) -> float:
        """Berechnet die gewichtete Cooldown-Zeit für die aktuelle Stunde."""
        base_cooldown = self.config.cameras[camera].notifications.cooldown
        hour = datetime.datetime.now().hour
        # Verwende normalisierte Gewichte (Bucket-Wert minus Minimum aller Buckets)
        weight = self._get_normalized_weight_count(camera, hour)
        
        # Verwende den dynamischen Gewichtsfaktor
        base_weight_factor = self.config.cameras[camera].notifications.weight_factor
        dynamic_weight_factor = self._get_dynamic_weight_factor(camera, base_weight_factor)
        
        weight_max_factor = self.config.cameras[camera].notifications.weight_max_factor
        weight_time_slots = self.config.cameras[camera].notifications.weight_time_slots
        
        # Berechne den Multiplikator mit dem dynamischen Faktor
        multiplier = 1 + weight * dynamic_weight_factor
        # Begrenze den Multiplikator auf das Maximum
        multiplier = min(multiplier, weight_max_factor)
        
        # Berechne die gewichtete Cooldown-Zeit
        weighted_cooldown = base_cooldown * multiplier
        
        # Berechne die maximale sinnvolle Cooldown-Zeit basierend auf der Bucket-Größe
        # Bei 24 time_slots = 24 Stunden am Tag = 3600 Sekunden pro Bucket
        seconds_per_bucket = 86400 / weight_time_slots  # 86400 = Sekunden pro Tag
        
        # Intelligentere Begrenzung: berücksichtige sowohl Bucket-Größe als auch Base-Cooldown
        bucket_limit = seconds_per_bucket * 0.8  # 80% der Bucket-Zeit als obere Grenze
        reasonable_minimum = base_cooldown * 0.5  # Mindestens 50% der Base-Cooldown
        max_reasonable_cooldown = max(bucket_limit, reasonable_minimum)
        
        # Begrenze die Cooldown-Zeit auf das sinnvolle Maximum
        final_cooldown = min(weighted_cooldown, max_reasonable_cooldown)
        
        if final_cooldown < weighted_cooldown:
            logger.debug(
                f"Cooldown for {camera} limited from {weighted_cooldown:.2f}s to {final_cooldown:.2f}s (bucket size limit: {max_reasonable_cooldown:.2f}s)"
            )
        
        return final_cooldown

    def _within_cooldown(self, camera: str) -> bool:
        now = datetime.datetime.now().timestamp()
        
        # Überprüfe ob kameraspezifische gewichtsbasierte Cooldown aktiviert ist
        camera_weight_enabled = (
            hasattr(self.config.cameras[camera].notifications, 'weight_factor') and
            self.config.cameras[camera].notifications.weight_factor > 0
        )
        
        # Globaler Cooldown - nur wenn kameraspezifische Cooldown NICHT aktiviert ist
        if not camera_weight_enabled and now - self.last_notification_time < self.config.notifications.cooldown:
            logger.debug(
                f"Skipping notification for {camera} - in global cooldown period"
            )
            return True
        # Kamera-spezifischer gewichteter Cooldown
        cooldown = self._get_weighted_cooldown(camera)
        if now - self.last_camera_notification_time[camera] < cooldown:
            current_weight = self._get_normalized_weight_count(camera, datetime.datetime.now().hour)
            base_weight_factor = self.config.cameras[camera].notifications.weight_factor
            dynamic_weight_factor = self._get_dynamic_weight_factor(camera, base_weight_factor)
            weight_max_factor = self.config.cameras[camera].notifications.weight_max_factor
            theoretical_multiplier = 1 + current_weight * dynamic_weight_factor
            actual_multiplier = min(theoretical_multiplier, weight_max_factor)
            capped = theoretical_multiplier > weight_max_factor
            
            factor_info = f"factor: {dynamic_weight_factor:.3f}"
            if abs(dynamic_weight_factor - base_weight_factor) > 0.001:
                factor_info += f" (base: {base_weight_factor:.3f})"
            
            logger.debug(
                f"Skipping notification for {camera} - in camera-specific weighted cooldown period ({cooldown:.2f}s, weight: {current_weight}, {factor_info}, multiplier: {actual_multiplier:.2f}{'[CAPPED]' if capped else ''})"
            )
            return True
        return False

    def _get_active_weights(self, camera: str, hour: int) -> list[float]:
        """Gibt alle noch aktiven (nicht abgelaufenen) Gewichte für eine Kamera und Stunde zurück."""
        now = datetime.datetime.now().timestamp()
        decay_days = self.config.cameras[camera].notifications.weight_decay_days
        decay_seconds = decay_days * 86400
        cutoff_time = now - decay_seconds
        
        # Filtere abgelaufene Timestamps heraus
        active_weights = [
            timestamp for timestamp in self.camera_weight_queues[camera][hour]
            if timestamp > cutoff_time
        ]
        
        # Aktualisiere die Queue, entferne abgelaufene Einträge
        self.camera_weight_queues[camera][hour] = active_weights
        
        return active_weights

    def _get_normalized_weight_count(self, camera: str, hour: int) -> int:
        """Gibt die normalisierte Anzahl der Gewichte zurück basierend auf Durchschnitt/Median."""
        # Sammle alle aktiven Gewichte für alle Stunden dieser Kamera
        all_bucket_counts = []
        time_slots = self.config.cameras[camera].notifications.weight_time_slots
        
        for h in range(time_slots):
            bucket_count = len(self._get_active_weights(camera, h))
            all_bucket_counts.append(bucket_count)
        
        # Berechne den aktuellen Bucket-Wert
        current_bucket_count = len(self._get_active_weights(camera, hour))
        
        # Verschiedene Normalisierungsansätze
        non_zero_counts = [count for count in all_bucket_counts if count > 0]
        
        if not non_zero_counts:
            return 0
        
        # Methode 1: Minimum der Non-Zero Buckets
        min_non_zero = min(non_zero_counts)
        
        # Methode 2: Durchschnitt aller Buckets (einschließlich Nullen)
        avg_all = sum(all_bucket_counts) / len(all_bucket_counts)
        
        # Methode 3: Median der Non-Zero Buckets
        sorted_non_zero = sorted(non_zero_counts)
        median_non_zero = sorted_non_zero[len(sorted_non_zero) // 2]
        
        # Wähle den Baseline-Wert: verwende das Minimum der aktiven Buckets
        # aber nur wenn es mehr als 1 aktiver Bucket ist
        if len(non_zero_counts) > 1:
            baseline = min_non_zero
        else:
            baseline = 0
        
        # Normalisiere nur wenn der aktuelle Bucket aktiv ist
        if current_bucket_count > 0:
            normalized_count = max(0, current_bucket_count - baseline)
        else:
            normalized_count = 0
        
        # Debug-Logging bei signifikanten Unterschieden
        if current_bucket_count != normalized_count and current_bucket_count > 0:
            logger.debug(
                f"Normalization for {camera}h{hour}: raw={current_bucket_count}, "
                f"normalized={normalized_count}, baseline={baseline}, "
                f"active_buckets={len(non_zero_counts)}"
            )
        
        return normalized_count

    def _increase_weight(self, camera: str):
        """Fügt einen neuen Gewichts-Timestamp für die aktuelle Stunde der Kamera hinzu."""
        hour = datetime.datetime.now().hour
        current_time = datetime.datetime.now().timestamp()
        self.camera_weight_queues[camera][hour].append(current_time)
        # Markiere, dass Änderungen vorliegen - Speicherung erfolgt batch-weise
        self.pending_weight_changes = True
        
        # Bei kritischen Situationen (viele Gewichte) sofort speichern
        if len(self.camera_weight_queues[camera][hour]) % 10 == 0:
            self._save_weights(force=True)

    def _decay_weights(self):
        """Entfernt automatisch abgelaufene Gewichte aus allen Queues."""
        weights_changed = False
        for camera in self.camera_weight_queues:
            for hour in range(self.config.cameras[camera].notifications.weight_time_slots):
                # _get_active_weights räumt automatisch abgelaufene Einträge auf
                old_count = len(self.camera_weight_queues[camera][hour])
                self._get_active_weights(camera, hour)
                new_count = len(self.camera_weight_queues[camera][hour])
                if old_count != new_count:
                    weights_changed = True
        
        # Speichere nur wenn sich etwas geändert hat
        if weights_changed:
            self.pending_weight_changes = True
            self._save_weights()

    def get_weight_statistics(self, camera: str) -> dict[str, Any]:
        """Gibt detaillierte Statistiken über Gewichte zurück für Debugging."""
        if camera not in self.camera_weight_queues:
            return {"error": f"Camera {camera} not found"}
        
        now = datetime.datetime.now()
        current_hour = now.hour
        
        # Aktuelle Gewichte sammeln (roh und normalisiert)
        active_weights = self._get_active_weights(camera, current_hour)
        normalized_current_weight = self._get_normalized_weight_count(camera, current_hour)
        total_weights_24h = 0
        total_normalized_weights_24h = 0
        hourly_breakdown = {}
        normalized_hourly_breakdown = {}
        
        for hour in range(24):
            weights_for_hour = self._get_active_weights(camera, hour)
            normalized_weights_for_hour = self._get_normalized_weight_count(camera, hour)
            hourly_breakdown[hour] = len(weights_for_hour)
            normalized_hourly_breakdown[hour] = normalized_weights_for_hour
            total_weights_24h += len(weights_for_hour)
            total_normalized_weights_24h += normalized_weights_for_hour
        
        # Cooldown-Berechnungen
        base_cooldown = self.config.cameras[camera].notifications.cooldown
        current_cooldown = self._get_weighted_cooldown(camera)
        base_weight_factor = self.config.cameras[camera].notifications.weight_factor
        dynamic_weight_factor = self._get_dynamic_weight_factor(camera, base_weight_factor)
        
        # Letzte Notification
        last_notification_time = self.last_camera_notification_time.get(camera, 0)
        time_since_last = now.timestamp() - last_notification_time if last_notification_time > 0 else None
        
        return {
            "camera": camera,
            "current_hour": current_hour,
            "active_weights_current_hour": len(active_weights),
            "normalized_weight_current_hour": normalized_current_weight,
            "total_weights_24h": total_weights_24h,
            "total_normalized_weights_24h": total_normalized_weights_24h,
            "hourly_breakdown": hourly_breakdown,
            "normalized_hourly_breakdown": normalized_hourly_breakdown,
            "cooldown": {
                "base": base_cooldown,
                "current": current_cooldown,
                "multiplier": current_cooldown / base_cooldown if base_cooldown > 0 else 0,
            },
            "weight_factors": {
                "base": base_weight_factor,
                "dynamic": dynamic_weight_factor,
                "adjustment": (dynamic_weight_factor - base_weight_factor) / base_weight_factor * 100 if base_weight_factor > 0 else 0,
            },
            "last_notification": {
                "timestamp": last_notification_time if last_notification_time > 0 else None,
                "seconds_ago": time_since_last,
                "formatted": datetime.datetime.fromtimestamp(last_notification_time).strftime('%Y-%m-%d %H:%M:%S') if last_notification_time > 0 else None,
            },
            "next_notification_allowed_in": max(0, current_cooldown - (time_since_last or float('inf'))),
        }

    def send_notification_test(self) -> None:
        if not self.config.notifications.email:
            return

        self.check_registrations()

        logger.debug("Sending test notification")

        for user in self.web_pushers:
            self.send_push_notification(
                user=user,
                payload={},
                title="Test Notification",
                message="This is a test notification from Frigate.",
                direct_url="/",
                notification_type="test",
            )

    def send_alert(self, payload: dict[str, Any]) -> None:
        if (
            not self.config.notifications.email
            or payload["after"]["severity"] != "alert"
        ):
            return

        camera: str = payload["after"]["camera"]
        current_time = datetime.datetime.now().timestamp()

        self._decay_weights()
        if self._within_cooldown(camera):
            return
        self._increase_weight(camera)
        
        # Debug-Information über aktuelle Gewichte
        hour = datetime.datetime.now().hour
        current_weight = self._get_normalized_weight_count(camera, hour)
        adjusted_cooldown = self._get_weighted_cooldown(camera)
        weight_factor = self.config.cameras[camera].notifications.weight_factor
        weight_max_factor = self.config.cameras[camera].notifications.weight_max_factor
        theoretical_multiplier = 1 + current_weight * weight_factor
        actual_multiplier = min(theoretical_multiplier, weight_max_factor)
        capped = theoretical_multiplier > weight_max_factor
        logger.debug(f"Alert notification sent for {camera} - normalized weight: {current_weight}, adjusted cooldown: {adjusted_cooldown:.2f}s, multiplier: {actual_multiplier:.2f}{'[CAPPED]' if capped else ''}")

        self.check_registrations()

        state = payload["type"]

        # Don't notify if message is an update and important fields don't have an update
        if (
            state == "update"
            and len(payload["before"]["data"]["objects"])
            == len(payload["after"]["data"]["objects"])
            and len(payload["before"]["data"]["zones"])
            == len(payload["after"]["data"]["zones"])
        ):
            logger.debug(
                f"Skipping notification for {camera} - message is an update and important fields don't have an update"
            )
            return

        self.last_camera_notification_time[camera] = current_time
        self.last_notification_time = current_time

        reviewId = payload["after"]["id"]
        sorted_objects: set[str] = set()

        for obj in payload["after"]["data"]["objects"]:
            if "-verified" not in obj:
                sorted_objects.add(obj)

        sorted_objects.update(payload["after"]["data"]["sub_labels"])

        title = f"{titlecase(', '.join(sorted_objects).replace('_', ' '))}{' was' if state == 'end' else ''} detected in {titlecase(', '.join(payload['after']['data']['zones']).replace('_', ' '))}"
        message = f"Detected on {titlecase(camera.replace('_', ' '))}"
        image = f"{payload['after']['thumb_path'].replace('/media/frigate', '')}"

        # if event is ongoing open to live view otherwise open to recordings view
        direct_url = f"/review?id={reviewId}" if state == "end" else f"/#{camera}"
        ttl = 3600 if state == "end" else 0

        logger.debug(f"Sending push notification for {camera}, review ID {reviewId}")

        for user in self.web_pushers:
            self.send_push_notification(
                user=user,
                payload=payload,
                title=title,
                message=message,
                direct_url=direct_url,
                image=image,
                ttl=ttl,
            )

        self.cleanup_registrations()

    def send_trigger(self, payload: dict[str, Any]) -> None:
        if not self.config.notifications.email:
            return

        camera: str = payload["camera"]
        camera_name: str = getattr(
            self.config.cameras[camera], "friendly_name", None
        ) or titlecase(camera.replace("_", " "))
        current_time = datetime.datetime.now().timestamp()

        self._decay_weights()
        if self._within_cooldown(camera):
            return
        self._increase_weight(camera)
        
        # Debug-Information über aktuelle Gewichte
        hour = datetime.datetime.now().hour
        current_weight = self._get_normalized_weight_count(camera, hour)
        adjusted_cooldown = self._get_weighted_cooldown(camera)
        weight_factor = self.config.cameras[camera].notifications.weight_factor
        weight_max_factor = self.config.cameras[camera].notifications.weight_max_factor
        theoretical_multiplier = 1 + current_weight * weight_factor
        actual_multiplier = min(theoretical_multiplier, weight_max_factor)
        capped = theoretical_multiplier > weight_max_factor
        logger.debug(f"Trigger notification sent for {camera} - normalized weight: {current_weight}, adjusted cooldown: {adjusted_cooldown:.2f}s, multiplier: {actual_multiplier:.2f}{'[CAPPED]' if capped else ''}")

        self.check_registrations()

        self.last_camera_notification_time[camera] = current_time
        self.last_notification_time = current_time

        trigger_type = payload["type"]
        event_id = payload["event_id"]
        name = payload["name"]
        score = payload["score"]

        title = f"{name.replace('_', ' ')} triggered on {camera_name}"
        message = f"{titlecase(trigger_type)} trigger fired for {camera_name} with score {score:.2f}"
        image = f"clips/triggers/{camera}/{event_id}.webp"

        direct_url = f"/explore?event_id={event_id}"
        ttl = 0

        logger.debug(
            f"Sending push notification for {camera_name}, trigger name {name}"
        )

        for user in self.web_pushers:
            self.send_push_notification(
                user=user,
                payload=payload,
                title=title,
                message=message,
                direct_url=direct_url,
                image=image,
                ttl=ttl,
            )

        self.cleanup_registrations()

    def stop(self) -> None:
        logger.info("Closing notification queue")
        # Speichere Gewichte vor dem Herunterfahren (erzwungen)
        self._save_weights(force=True)
        self.notification_thread.join()
