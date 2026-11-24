const KEY = 'aegis-admin-token';

// sessionStorage: mất khi đóng tab. Có thể bị chặn (chế độ riêng tư) nên luôn bọc try/catch.
export const tokenStorage = {
  get(): string | null {
    try { return sessionStorage.getItem(KEY); } catch { return null; }
  },
  set(token: string) {
    try { sessionStorage.setItem(KEY, token); } catch { /* bỏ qua */ }
  },
  clear() {
    try { sessionStorage.removeItem(KEY); } catch { /* bỏ qua */ }
  },
};
