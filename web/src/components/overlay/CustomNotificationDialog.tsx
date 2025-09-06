import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import {
    Form,
    FormControl,
    FormDescription,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { zodResolver } from "@hookform/resolvers/zod";
import axios from "axios";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { LuSend } from "react-icons/lu";
import { toast } from "sonner";
import { z } from "zod";
import ActivityIndicator from "@/components/indicators/activity-indicator";

const notificationSchema = z.object({
    title: z.string().min(1, "Title is required").max(200, "Title too long"),
    message: z.string().min(1, "Message is required").max(500, "Message too long"),
    direct_url: z.string().optional(),
    image: z.string().optional(),
    ttl: z.number().int().min(0).max(86400).optional(),
});

type NotificationFormValues = z.infer<typeof notificationSchema>;

export default function CustomNotificationButton() {
    const [open, setOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(false);

    const form = useForm<NotificationFormValues>({
        resolver: zodResolver(notificationSchema),
        defaultValues: {
            title: "",
            message: "",
            direct_url: "",
            image: "",
            ttl: 0,
        },
    });

    const onSubmit = async (values: NotificationFormValues) => {
        setIsLoading(true);
        try {
            const response = await axios.post("/api/notifications/send", values);

            if (response.status === 200) {
                toast.success(response.data.message, {
                    position: "top-center",
                });
                form.reset();
                setOpen(false);
            }
        } catch (error: any) {
            const errorMessage =
                error.response?.data?.message || "Failed to send notification";
            toast.error(errorMessage, {
                position: "top-center",
            });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="outline" className="gap-2">
                    <LuSend className="size-4" />
                    Send Custom Notification
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Send Custom Notification</DialogTitle>
                </DialogHeader>
                <Form {...form}>
                    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                        <FormField
                            control={form.control}
                            name="title"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Title *</FormLabel>
                                    <FormControl>
                                        <Input
                                            placeholder="Enter notification title"
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        <FormField
                            control={form.control}
                            name="message"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Message *</FormLabel>
                                    <FormControl>
                                        <Textarea
                                            placeholder="Enter notification message"
                                            className="resize-none"
                                            rows={3}
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        <FormField
                            control={form.control}
                            name="direct_url"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Direct URL (optional)</FormLabel>
                                    <FormControl>
                                        <Input
                                            placeholder="/cameras or https://example.com"
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormDescription>
                                        URL to open when notification is clicked
                                    </FormDescription>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        <FormField
                            control={form.control}
                            name="image"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Image URL (optional)</FormLabel>
                                    <FormControl>
                                        <Input
                                            placeholder="https://example.com/image.jpg"
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormDescription>
                                        Image to display in notification
                                    </FormDescription>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        <FormField
                            control={form.control}
                            name="ttl"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>TTL (seconds, optional)</FormLabel>
                                    <FormControl>
                                        <Input
                                            type="number"
                                            placeholder="0"
                                            {...field}
                                            onChange={(e) => field.onChange(Number(e.target.value))}
                                        />
                                    </FormControl>
                                    <FormDescription>
                                        Time to live (0 = no expiration, max 86400)
                                    </FormDescription>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        <div className="flex justify-end gap-2">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setOpen(false)}
                                disabled={isLoading}
                            >
                                Cancel
                            </Button>
                            <Button type="submit" disabled={isLoading}>
                                {isLoading ? (
                                    <div className="flex items-center gap-2">
                                        <ActivityIndicator />
                                        Sending...
                                    </div>
                                ) : (
                                    <>
                                        <LuSend className="size-4 mr-2" />
                                        Send Notification
                                    </>
                                )}
                            </Button>
                        </div>
                    </form>
                </Form>
            </DialogContent>
        </Dialog>
    );
}
