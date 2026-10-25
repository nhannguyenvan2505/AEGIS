import * as SecureStore from 'expo-secure-store';
const key = 'aegis.accessToken';
export const tokenStorage = {
  get: () => SecureStore.getItemAsync(key),
  set: (token: string) => SecureStore.setItemAsync(key, token),
  clear: () => SecureStore.deleteItemAsync(key),
};
