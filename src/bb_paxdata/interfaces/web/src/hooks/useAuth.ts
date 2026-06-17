import { useAuthStore } from '@/store/authStore';

export const useAuth = () => {
  const { user, isAuthenticated, login, logout, hasPermission } = useAuthStore();
  return { user, isAuthenticated, login, logout, hasPermission };
};
