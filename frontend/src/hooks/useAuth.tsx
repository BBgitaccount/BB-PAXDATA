// frontend/src/hooks/useAuth.tsx
import React, { createContext, useContext, useEffect, useState } from 'react';

export interface UserSession {
  userId: string;
  roles: string[];
  csrfToken?: string;
}

interface AuthContextType {
  user: UserSession | null;
  loading: boolean;
  login: (userId: string, roles: string[]) => void;
  logout: () => Promise<void>;
  refreshSession: () => Promise<boolean>;
  hasRole: (requiredRoles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserSession | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Sync token and roles on mount
  useEffect(() => {
    const initAuth = async () => {
      try {
        const success = await refreshSession();
        if (!success) {
          setUser(null);
        }
      } catch (err) {
        console.error('Failed to initialize session:', err);
      } finally {
        setLoading(false);
      }
    };
    initAuth();
  }, []);

  const login = (userId: string, roles: string[]) => {
    setUser({ userId, roles });
  };

  const logout = async () => {
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST' });
    } catch (err) {
      console.error('Logout request failed:', err);
    } finally {
      setUser(null);
    }
  };

  const refreshSession = async (): Promise<boolean> => {
    try {
      const response = await fetch('/api/v1/auth/refresh', { method: 'POST' });
      if (response.ok) {
        const data = await response.json();
        setUser({
          userId: data.reviewer_id,
          roles: data.roles,
          csrfToken: data.csrf_token,
        });
        return true;
      }
    } catch (err) {
      console.error('Token rotation failed:', err);
    }
    return false;
  };

  const hasRole = (requiredRoles: string[]): boolean => {
    if (!user) return false;
    // Admins bypass all role requirements
    if (user.roles.includes('admin')) return true;
    return requiredRoles.some((role) => user.roles.includes(role));
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshSession, hasRole }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Route and component guard for authorization
interface GuardProps {
  allowedRoles: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const AuthorityGuard: React.FC<GuardProps> = ({
  allowedRoles,
  children,
  fallback = <div className="forbidden-notice">Access Denied: Insufficient Permissions</div>,
}) => {
  const { hasRole, loading } = useAuth();

  if (loading) {
    return <div className="auth-spinner">Loading authorization...</div>;
  }

  return hasRole(allowedRoles) ? <>{children}</> : <>{fallback}</>;
};
