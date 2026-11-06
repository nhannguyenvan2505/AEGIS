export type FieldErrors<T> = Partial<Record<keyof T, string>>;

export type LoginValues = { email: string; password: string };
export type RegisterValues = LoginValues & { fullName: string; confirmPassword: string };
export type ChangePasswordValues = {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
};

function validateEmail(email: string): string | undefined {
  const value = email.trim();
  if (!value) return 'Vui lòng nhập email.';
  if (!/^[^\s@.]+(?:\.[^\s@.]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$/i.test(value)) {
    return 'Email không đúng định dạng.';
  }
}

function validatePassword(password: string, label: string, minimumLength = false): string | undefined {
  if (!password.trim()) return `Vui lòng nhập ${label}.`;
  if (minimumLength && (password.length < 12 || password.length > 128)) return 'Mật khẩu phải có từ 12 đến 128 ký tự.';
}

export function validateLogin(values: LoginValues): FieldErrors<LoginValues> {
  return {
    email: validateEmail(values.email),
    password: validatePassword(values.password, 'mật khẩu'),
  };
}

export function validateRegister(values: RegisterValues): FieldErrors<RegisterValues> {
  return {
    fullName: values.fullName.trim() ? undefined : 'Vui lòng nhập họ và tên.',
    email: validateEmail(values.email),
    password: validatePassword(values.password, 'mật khẩu', true),
    confirmPassword: !values.confirmPassword.trim()
      ? 'Vui lòng xác nhận mật khẩu.'
      : values.confirmPassword !== values.password ? 'Mật khẩu xác nhận không trùng khớp.' : undefined,
  };
}

export function validateChangePassword(values: ChangePasswordValues): FieldErrors<ChangePasswordValues> {
  return {
    currentPassword: validatePassword(values.currentPassword, 'mật khẩu hiện tại'),
    newPassword: validatePassword(values.newPassword, 'mật khẩu mới', true),
    confirmPassword: !values.confirmPassword.trim()
      ? 'Vui lòng xác nhận mật khẩu mới.'
      : values.confirmPassword !== values.newPassword ? 'Mật khẩu mới xác nhận không trùng khớp.' : undefined,
  };
}
