import {
    AlertDialog,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useTranslation } from "react-i18next";

type ActionConfirmationDialogProps = {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    actionName: string;
    onConfirm: () => void;
    isExecuting: boolean;
};

export default function ActionConfirmationDialog({
    open,
    onOpenChange,
    actionName,
    onConfirm,
    isExecuting,
}: ActionConfirmationDialogProps) {
    const { t } = useTranslation("common");

    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>
                        {t("confirmAction", { defaultValue: "Confirm Action" })}
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                        {t("confirmActionDescription", {
                            defaultValue: 'Are you sure you want to execute "{{actionName}}"?',
                            actionName,
                        })}
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel disabled={isExecuting}>
                        {t("button.cancel")}
                    </AlertDialogCancel>
                    <Button
                        variant="default"
                        onClick={onConfirm}
                        disabled={isExecuting}
                    >
                        {isExecuting
                            ? t("button.executing", { defaultValue: "Executing..." })
                            : t("button.confirm", { defaultValue: "Confirm" })}
                    </Button>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
}
