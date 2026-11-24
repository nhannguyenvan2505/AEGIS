export type ProfileValues = { fullName: string; email: string; phone: string };
export type EditableProfileValues = Pick<ProfileValues, 'fullName' | 'phone'>;
export type PersonalProfile = ProfileValues & { avatarUri: string | null };
export type ProfileErrors = Partial<Record<keyof ProfileValues, string>>;
export type ProfileStorage = { get: (key: string) => Promise<string | null>; set: (key: string, value: string) => Promise<void> };

export function normalizeProfile(values: ProfileValues): ProfileValues {
  return { fullName: values.fullName.trim().replace(/\s+/g, ' '), email: values.email.trim(), phone: values.phone.replace(/[\s().-]/g, '') };
}

export function validateProfile(values: ProfileValues): ProfileErrors {
  const value = normalizeProfile(values);
  const errors: ProfileErrors = {};
  if (!value.fullName) errors.fullName = 'Vui lòng nhập họ và tên.';
  else if (value.fullName.length > 120) errors.fullName = 'Họ và tên tối đa 120 ký tự.';
  if (!value.email) errors.email = 'Vui lòng nhập email.';
  else if (value.email.length > 254 || !/^[^\s@.]+(?:\.[^\s@.]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$/i.test(value.email)) {
    errors.email = 'Email chưa đúng. Ví dụ: minh@example.com.';
  }
  if (!/^0\d{9}$/.test(value.phone)) errors.phone = 'Nhập 10 chữ số, bắt đầu bằng số 0.';
  return errors;
}

export const profileNamespace = (userId: string) => Array.from(userId).map(character => character.codePointAt(0)!.toString(16)).join('-');
export const profileKey = (userId: string) => `aegis.profile.v1.${profileNamespace(userId)}`;
export const emptyProfile = (email: string): PersonalProfile => ({ fullName: '', email, phone: '', avatarUri: null });
export const profileName = (profile: PersonalProfile) => profile.fullName || 'Người dùng AEGIS';
export const profileInitial = (profile: PersonalProfile) => (profile.fullName.split(' ').filter(Boolean).at(-1)?.[0] || profile.email[0] || 'A').toLocaleUpperCase('vi-VN');
export const profilePhone = (phone: string) => /^0\d{9}$/.test(phone) ? `${phone.slice(0, 4)} ${phone.slice(4, 7)} ${phone.slice(7)}` : 'Chưa cập nhật';
const validAvatar = (uri: unknown) => uri === null || (typeof uri === 'string' && uri.startsWith('file://'));

export function createProfileRepository(storage: ProfileStorage) {
  async function read(userId: string, loginEmail: string): Promise<PersonalProfile> {
    const raw = await storage.get(profileKey(userId));
    if (!raw) return emptyProfile(loginEmail);
    const saved = JSON.parse(raw);
    if (saved?.version !== 1 || saved.owner !== userId || !saved.profile ||
        !['fullName', 'email', 'phone'].every(key => typeof saved.profile[key] === 'string') ||
        !validAvatar(saved.profile.avatarUri) ||
        Object.keys(validateProfile(saved.profile)).length) {
      throw new Error('Chưa đọc được hồ sơ đã lưu. Vui lòng thử tải lại.');
    }
    return { ...normalizeProfile(saved.profile), email: loginEmail, avatarUri: saved.profile.avatarUri };
  }
  async function save(userId: string, profile: PersonalProfile, loginEmail: string) {
    if (profile.email.trim() !== loginEmail) throw new Error('Email đăng nhập không thể thay đổi trong hồ sơ.');
    if (Object.keys(validateProfile(profile)).length || !validAvatar(profile.avatarUri)) throw new Error('Vui lòng kiểm tra lại thông tin hồ sơ.');
    const value: PersonalProfile = { ...normalizeProfile(profile), email: loginEmail, avatarUri: profile.avatarUri };
    await storage.set(profileKey(userId), JSON.stringify({ version: 1, owner: userId, profile: value }));
    return value;
  }
  return { read, save };
}
