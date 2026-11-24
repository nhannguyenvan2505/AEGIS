import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { useAuth } from '../../state/AuthContext';
import { useDemo } from '../../state/DemoContext';
import { emptyProfile, validateProfile, type PersonalProfile, type EditableProfileValues } from './profileModel';
import { persistProfileAvatar, profileRepository } from './profileStorage';

type ProfileState = {
  profile: PersonalProfile; loading: boolean; error: string; saving: boolean; loginEmail: string; authenticated: boolean;
  reload: () => void; save: (values: EditableProfileValues, avatarUri: string | null) => Promise<PersonalProfile>;
};
const Context = createContext<ProfileState | null>(null);

function ScopedProfileProvider({ userId, loginEmail, children }: { userId?: string; loginEmail: string; children: ReactNode }) {
  const [profile, setProfile] = useState(() => emptyProfile(loginEmail));
  const [loading, setLoading] = useState(!!userId);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const current = useRef(profile);
  const active = useRef(true);
  const writing = useRef(false);
  const sequence = useRef(0);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const reload = useCallback(() => {
    if (!userId || writing.current) return;
    const request = ++sequence.current;
    setLoading(true); setError('');
    void profileRepository.read(userId, loginEmail).then(value => {
      if (active.current && request === sequence.current) { current.current = value; setProfile(value); }
    }).catch(() => {
      if (active.current && request === sequence.current) setError('Chưa tải được hồ sơ trên thiết bị. Vui lòng thử lại.');
    }).finally(() => { if (active.current && request === sequence.current) setLoading(false); });
  }, [userId, loginEmail]);
  useEffect(reload, [reload]);

  async function save(values: EditableProfileValues, avatarUri: string | null) {
    if (!userId) throw new Error('Vui lòng đăng nhập để lưu hồ sơ.');
    if (writing.current || loading || error) throw new Error('Chưa thể lưu hồ sơ. Vui lòng thử lại.');
    const candidate = { ...values, email: loginEmail };
    if (Object.keys(validateProfile(candidate)).length) throw new Error('Vui lòng kiểm tra lại thông tin.');
    writing.current = true; sequence.current++; setSaving(true);
    try {
      const savedAvatar = avatarUri && avatarUri !== current.current.avatarUri ? await persistProfileAvatar(userId, avatarUri) : avatarUri;
      const saved = await profileRepository.save(userId, { ...candidate, avatarUri: savedAvatar }, loginEmail);
      if (active.current) { current.current = saved; setProfile(saved); }
      return saved;
    } finally { writing.current = false; if (active.current) setSaving(false); }
  }
  return <Context.Provider value={{ profile: { ...profile, email: loginEmail }, loading, error, saving, loginEmail, authenticated: !!userId, reload, save }}>{children}</Context.Provider>;
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const { generation } = useDemo();
  return <ScopedProfileProvider key={session?.user.id ?? `profile-guest-${generation}`} userId={session?.user.id} loginEmail={session?.user.email ?? ''}>{children}</ScopedProfileProvider>;
}

export function useProfile() {
  const value = useContext(Context);
  if (!value) throw new Error('Missing ProfileProvider');
  return value;
}
