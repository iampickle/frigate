import { useState } from "react";
import { FaPlay } from "react-icons/fa";
import { toast } from "sonner";
import axios from "axios";
import { CameraConfig } from "@/types/frigateConfig";
import CameraFeatureToggle from "./CameraFeatureToggle";
import { getActionIcon } from "./ActionIconMap";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

type CameraActionsProps = {
    camera: CameraConfig;
    fullscreen: boolean;
    cameraEnabled: boolean;
};

export default function CameraActions({
    camera,
    fullscreen,
    cameraEnabled,
}: CameraActionsProps) {
    const [executingAction, setExecutingAction] = useState<string | null>(null);

    // Don't render if no actions are configured
    if (!camera.actions?.actions || camera.actions.actions.length === 0) {
        return null;
    }

    const executeAction = async (actionName: string) => {
        setExecutingAction(actionName);
        try {
            const response = await axios.post(
                `camera/${camera.name}/actions/${actionName}/trigger`
            );

            if (response.data.success) {
                toast.success(`Action "${actionName}" executed successfully`, {
                    position: "top-center",
                    duration: 3000,
                });
            } else {
                toast.error(response.data.message || `Failed to execute action "${actionName}"`, {
                    position: "top-center",
                    duration: 5000,
                });
            }
        } catch (error) {
            console.error("Error executing camera action:", error);
            toast.error(`Failed to execute action "${actionName}"`, {
                position: "top-center",
                duration: 5000,
            });
        } finally {
            setExecutingAction(null);
        }
    };

    const actions = camera.actions.actions;

    // Separate standalone buttons from dropdown actions
    const standaloneActions = actions.filter(action => action.standalone);
    const dropdownActions = actions.filter(action => !action.standalone);

    const renderDropdownMenu = () => {
        if (dropdownActions.length === 0) return null;

        return (
            <DropdownMenu key="dropdown-menu">
                <DropdownMenuTrigger>
                    <div
                        className={cn(
                            "flex flex-col items-center justify-center rounded-lg bg-secondary p-2 text-secondary-foreground md:p-0",
                            fullscreen && "rounded-full bg-gradient-to-br from-gray-400 to-gray-500 bg-gray-500"
                        )}
                    >
                        <FaPlay className="size-5 text-secondary-foreground md:m-[6px]" />
                    </div>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                    {dropdownActions.map((action) => {
                        const isExecuting = executingAction === action.name;
                        const ActionIcon = getActionIcon(action.icon);
                        return (
                            <DropdownMenuItem
                                key={action.name}
                                className={cn(
                                    "cursor-pointer flex items-center gap-2",
                                    isExecuting && "animate-pulse",
                                    !cameraEnabled && "opacity-50 cursor-not-allowed"
                                )}
                                disabled={!cameraEnabled || isExecuting}
                                onSelect={() => {
                                    if (cameraEnabled && !isExecuting) {
                                        executeAction(action.name);
                                    }
                                }}
                            >
                                <ActionIcon className="size-4" />
                                {isExecuting ? `Executing ${action.name}...` : action.name}
                            </DropdownMenuItem>
                        );
                    })}
                </DropdownMenuContent>
            </DropdownMenu>
        );
    };

    // Render all buttons and dropdown as an array to avoid Fragment issues
    const components = [
        ...standaloneActions.map((action) => {
            const isExecuting = executingAction === action.name;
            const ActionIcon = getActionIcon(action.icon);

            return (
                <CameraFeatureToggle
                    className={cn(
                        "p-2 md:p-0",
                        isExecuting && "animate-pulse"
                    )}
                    variant={fullscreen ? "overlay" : "primary"}
                    Icon={ActionIcon}
                    isActive={isExecuting}
                    title={isExecuting ? `Executing ${action.name}...` : action.name}
                    onClick={() => executeAction(action.name)}
                    disabled={!cameraEnabled || isExecuting}
                />
            );
        }),
        renderDropdownMenu()
    ].filter(Boolean);

    // If only one component, return it directly
    if (components.length === 1) {
        return components[0];
    }

    // Multiple components, return them all
    return components;
}
