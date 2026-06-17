import { useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { useUIStore } from '@/store/uiStore';
import { Eye, EyeOff } from 'lucide-react';
import { cn } from '@/utils/helpers';

export const LoginForm = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);
  const addToast = useUIStore((s) => s.addToast);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      addToast({ type: 'error', message: 'E-posta ve şifre gereklidir.' });
      return;
    }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 800));
    const mockToken = `mock-jwt-token:${email}:admin`;
    localStorage.setItem('paxdata_token', mockToken);
    login({
      reviewer_id: email,
      roles: ['admin'],
      token: mockToken,
      scope_type: 'global',
      scope_value: '*',
    });
    addToast({ type: 'success', message: 'Kimlik doğrulama başarılı.' });
    setLoading(false);
  };

  return (
    <div className="w-full max-w-md">
      <div className="mb-12">
        <h1 className="text-2xl font-semibold tracking-tight text-carbon-50 mb-2">PAXDATA</h1>
        <p className="text-sm text-carbon-400 tracking-tight">Human-in-the-Loop Özet</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="label-micro mb-2 block">E-posta</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2.5 text-sm bg-carbon-900 border border-hair border-carbon-550 focus:border-carbon-300 transition-colors"
            placeholder="reviewer@paxdata.int"
          />
        </div>

        <div>
          <label className="label-micro mb-2 block">Şifre</label>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2.5 text-sm bg-carbon-900 border border-hair border-carbon-550 focus:border-carbon-300 transition-colors pr-10"
              placeholder="••••••••"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-carbon-400 hover:text-carbon-200"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className={cn('w-full btn-primary py-3', loading && 'opacity-50 cursor-not-allowed')}
        >
          {loading ? 'DOĞRULANIYOR...' : 'GİRİŞ YAP'}
        </button>
      </form>

      <div className="mt-8 pt-6 border-t border-hair border-carbon-550">
        <p className="text-2xs text-carbon-500 tracking-diplomatic">
          Sisteme erişim, rol bazlı yetkilendirme (RBAC) ile kontrol edilir. Tüm oturumlar
          denetlenir.
        </p>
      </div>
    </div>
  );
};
