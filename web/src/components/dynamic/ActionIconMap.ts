import { IconType } from "react-icons";
import {
    FaLightbulb,
    FaBell,
    FaBullhorn,  // Replacing FaSiren
    FaLock,
    FaUnlock,
    FaPlay,
    FaPause,
    FaStop,
    FaPowerOff,
    FaHome,
    FaCar,
    FaCamera,
    FaVolumeUp,
    FaVolumeMute,
    FaVideo,
    FaVideoSlash,
    FaBolt,
    FaShieldAlt,  // Replacing FaShield
    FaEye,
    FaEyeSlash,
    FaToggleOn,
    FaToggleOff,
    FaWifi,
    FaTimes,  // Replacing FaWifiSlash
    FaRecordVinyl,
    FaMicrophone,
    FaMicrophoneSlash,
    FaPhoneVolume,
    FaClock,  // Replacing FaAlarmClock
    FaExclamationTriangle,
    FaCheckCircle,
    FaTimesCircle,
    FaArrowUp,
    FaArrowDown,
    FaArrowLeft,
    FaArrowRight,
    FaExpand,
    FaCompress,
    FaSearchPlus,
    FaSearchMinus,
    FaCog,
    FaTrash,
    FaEdit,
    FaSave,
    FaRedo,  // Replacing FaRefresh
    FaSync,
    FaDownload,
    FaUpload,
} from "react-icons/fa";
import {
    MdLightMode,
    MdDarkMode,
    MdNotifications,
    MdNotificationsOff,
    MdSecurity,
    MdLock,
    MdLockOpen,
    MdAlarm,
    MdAlarmOff,
    MdVolumeUp,
    MdVolumeOff,
    MdPlayArrow,
    MdPause,
    MdStop,
    MdPowerSettingsNew,
    MdHome,
    MdDirectionsCar,
    MdCamera,
    MdCameraAlt,
    MdFlashOn,
    MdFlashOff,
    MdVisibility,
    MdVisibilityOff,
    MdWifi,
    MdWifiOff,
    MdMic,
    MdMicOff,
    MdPhone,
    MdPhoneDisabled,
    MdWarning,
    MdCheckCircle,
    MdCancel,
    MdKeyboardArrowUp,
    MdKeyboardArrowDown,
    MdKeyboardArrowLeft,
    MdKeyboardArrowRight,
    MdFullscreen,
    MdFullscreenExit,
    MdZoomIn,
    MdZoomOut,
    MdSettings,
    MdDelete,
    MdEdit,
    MdSave,
    MdRefresh,
    MdSync,
    MdDownload,
    MdUpload,
} from "react-icons/md";
import {
    LuLightbulb,
    LuBell,
    LuMegaphone,  // Replacing LuSiren
    LuLock,
    LuLockOpen,   // Replacing LuUnlock  
    LuPlay,
    LuPause,
    LuSquare,     // Replacing LuStop
    LuPower,
    LuHouse,      // Replacing LuHome
    LuCar,
    LuCamera,
    LuVolumeX,
    LuVolume2,
    LuVideo,
    LuVideoOff,
    LuZap,
    LuShield,
    LuEye,
    LuEyeOff,
    LuToggleLeft,
    LuToggleRight,
    LuWifi,
    LuWifiOff,
    LuMic,
    LuMicOff,
    LuPhone,
    LuPhoneOff,
    LuClock,      // Replacing LuAlarmClock
    LuTriangleAlert,  // Replacing LuAlertTriangle
    LuCircleCheck,    // Replacing LuCheckCircle
    LuCircleX,        // Replacing LuXCircle
    LuArrowUp,
    LuArrowDown,
    LuArrowLeft,
    LuArrowRight,
    LuExpand,
    LuShrink,
    LuZoomIn,
    LuZoomOut,
    LuSettings,
    LuTrash,
    LuPencil,     // Replacing LuEdit
    LuSave,
    LuRefreshCw,
    LuDownload,
    LuUpload,
} from "react-icons/lu";

// Icon mapping for camera actions
const ICON_MAP: Record<string, IconType> = {
    // FontAwesome icons
    FaLightbulb,
    FaBell,
    FaBullhorn,  // Siren replacement
    FaLock,
    FaUnlock,
    FaPlay,
    FaPause,
    FaStop,
    FaPowerOff,
    FaHome,
    FaCar,
    FaCamera,
    FaVolumeUp,
    FaVolumeMute,
    FaVideo,
    FaVideoSlash,
    FaBolt,
    FaShieldAlt,  // Shield replacement
    FaEye,
    FaEyeSlash,
    FaToggleOn,
    FaToggleOff,
    FaWifi,
    FaTimes,  // WiFi slash replacement
    FaRecordVinyl,
    FaMicrophone,
    FaMicrophoneSlash,
    FaPhoneVolume,
    FaClock,  // Alarm clock replacement
    FaExclamationTriangle,
    FaCheckCircle,
    FaTimesCircle,
    FaArrowUp,
    FaArrowDown,
    FaArrowLeft,
    FaArrowRight,
    FaExpand,
    FaCompress,
    FaSearchPlus,
    FaSearchMinus,
    FaCog,
    FaTrash,
    FaEdit,
    FaSave,
    FaRedo,  // Refresh replacement
    FaSync,
    FaDownload,
    FaUpload,

    // Material Design icons
    MdLightMode,
    MdDarkMode,
    MdNotifications,
    MdNotificationsOff,
    MdSecurity,
    MdLock,
    MdLockOpen,
    MdAlarm,
    MdAlarmOff,
    MdVolumeUp,
    MdVolumeOff,
    MdPlayArrow,
    MdPause,
    MdStop,
    MdPowerSettingsNew,
    MdHome,
    MdDirectionsCar,
    MdCamera,
    MdCameraAlt,
    MdFlashOn,
    MdFlashOff,
    MdVisibility,
    MdVisibilityOff,
    MdWifi,
    MdWifiOff,
    MdMic,
    MdMicOff,
    MdPhone,
    MdPhoneDisabled,
    MdWarning,
    MdCheckCircle,
    MdCancel,
    MdKeyboardArrowUp,
    MdKeyboardArrowDown,
    MdKeyboardArrowLeft,
    MdKeyboardArrowRight,
    MdFullscreen,
    MdFullscreenExit,
    MdZoomIn,
    MdZoomOut,
    MdSettings,
    MdDelete,
    MdEdit,
    MdSave,
    MdRefresh,
    MdSync,
    MdDownload,
    MdUpload,

    // Lucide icons
    LuLightbulb,
    LuBell,
    LuMegaphone,      // Siren replacement
    LuLock,
    LuLockOpen,       // Unlock replacement
    LuPlay,
    LuPause,
    LuSquare,         // Stop replacement
    LuPower,
    LuHouse,          // Home replacement
    LuCar,
    LuCamera,
    LuVolumeX,
    LuVolume2,
    LuVideo,
    LuVideoOff,
    LuZap,
    LuShield,
    LuEye,
    LuEyeOff,
    LuToggleLeft,
    LuToggleRight,
    LuWifi,
    LuWifiOff,
    LuMic,
    LuMicOff,
    LuPhone,
    LuPhoneOff,
    LuClock,          // Alarm clock replacement
    LuTriangleAlert,  // Alert triangle replacement
    LuCircleCheck,    // Check circle replacement
    LuCircleX,        // X circle replacement
    LuArrowUp,
    LuArrowDown,
    LuArrowLeft,
    LuArrowRight,
    LuExpand,
    LuShrink,
    LuZoomIn,
    LuZoomOut,
    LuSettings,
    LuTrash,
    LuPencil,         // Edit replacement
    LuSave,
    LuRefreshCw,
    LuDownload,
    LuUpload,
};

/**
 * Get an icon component by name
 * @param iconName - The name of the icon (e.g., 'FaLightbulb', 'MdHome', 'LuCamera')
 * @returns The icon component or FaPlay as fallback
 */
export function getActionIcon(iconName?: string): IconType {
    if (!iconName) {
        return FaPlay; // Default fallback icon
    }

    const IconComponent = ICON_MAP[iconName];
    if (IconComponent) {
        return IconComponent;
    }

    // Fallback to FaPlay if icon not found
    console.warn(`Icon "${iconName}" not found in ICON_MAP. Using FaPlay as fallback.`);
    return FaPlay;
}

/**
 * Get available icon names for documentation/configuration
 */
export function getAvailableIcons(): string[] {
    return Object.keys(ICON_MAP).sort();
}

/**
 * Icon categories for better organization
 */
export const ICON_CATEGORIES = {
    "Lighting": ["FaLightbulb", "MdLightMode", "MdDarkMode", "LuLightbulb", "MdFlashOn", "MdFlashOff"],
    "Security": ["FaLock", "FaUnlock", "FaShield", "MdLock", "MdLockOpen", "MdSecurity", "LuLock", "LuUnlock", "LuShield"],
    "Audio/Video": ["FaCamera", "FaVideo", "FaVideoSlash", "FaVolumeUp", "FaVolumeMute", "FaMicrophone", "FaMicrophoneSlash", "MdCamera", "MdCameraAlt", "MdVolumeUp", "MdVolumeOff", "LuCamera", "LuVideo", "LuVideoOff", "LuVolume2", "LuVolumeX"],
    "Alerts": ["FaBell", "FaSiren", "FaAlarmClock", "FaExclamationTriangle", "MdNotifications", "MdAlarm", "MdWarning", "LuBell", "LuSiren", "LuAlarmClock", "LuAlertTriangle"],
    "Power/Control": ["FaPowerOff", "FaPlay", "FaPause", "FaStop", "FaToggleOn", "FaToggleOff", "MdPowerSettingsNew", "MdPlayArrow", "MdPause", "MdStop", "LuPower", "LuPlay", "LuPause", "LuStop", "LuToggleLeft", "LuToggleRight"],
    "Network": ["FaWifi", "FaWifiSlash", "FaPhone", "MdWifi", "MdWifiOff", "MdPhone", "MdPhoneDisabled", "LuWifi", "LuWifiOff", "LuPhone", "LuPhoneOff"],
    "Navigation": ["FaArrowUp", "FaArrowDown", "FaArrowLeft", "FaArrowRight", "FaExpand", "FaCompress", "MdKeyboardArrowUp", "MdKeyboardArrowDown", "MdKeyboardArrowLeft", "MdKeyboardArrowRight", "MdFullscreen", "MdFullscreenExit", "LuArrowUp", "LuArrowDown", "LuArrowLeft", "LuArrowRight", "LuExpand", "LuShrink"],
    "General": ["FaHome", "FaCar", "FaEye", "FaEyeSlash", "FaCog", "MdHome", "MdDirectionsCar", "MdVisibility", "MdVisibilityOff", "MdSettings", "LuHome", "LuCar", "LuEye", "LuEyeOff", "LuSettings"]
} as const;
