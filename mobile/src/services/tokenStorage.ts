import * as SecureStore from 'expo-secure-store';
const key = 'aegis.accessToken';
// Preserve the order of expiry/logout and a subsequent login on native storage.
let writes: Promise<void> = Promise.resolve();
function write(operation: () => Promise<void>) {
  const task = writes.then(operation);
  writes = task.catch(() => {});
  return task;
}
export const tokenStorage = {
  get: () => writes.then(() => SecureStore.getItemAsync(key)),
  set: (token: string) => write(() => SecureStore.setItemAsync(key, token)),
  clear: () => write(() => SecureStore.deleteItemAsync(key)),
};
