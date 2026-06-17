import { useUIStore } from '@/store/uiStore';

export const useToast = () => {
  const addToast = useUIStore((s) => s.addToast);
  return {
    success: (message: string) => addToast({ type: 'success', message }),
    error: (message: string) => addToast({ type: 'error', message }),
    warning: (message: string) => addToast({ type: 'warning', message }),
    info: (message: string) => addToast({ type: 'info', message }),
  };
};
