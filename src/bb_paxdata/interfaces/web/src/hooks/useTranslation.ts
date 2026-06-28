import { en } from '@/i18n/en';
import { tr } from '@/i18n/tr';
import { useUIStore } from '@/store/uiStore';

const dictionaries = { tr, en };

export const useTranslation = () => {
  const language = useUIStore((s) => s.language);
  const setLanguage = useUIStore((s) => s.setLanguage);

  const t = (key: keyof typeof tr) => {
    const dict = dictionaries[language] || dictionaries.tr;
    return dict[key] || key;
  };

  return { t, language, setLanguage };
};
