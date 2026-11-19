import * as SecureStore from 'expo-secure-store';
import { Directory, File, Paths } from 'expo-file-system';
import { uuid } from 'expo-modules-core';
import { createProfileRepository, profileNamespace } from './profileModel';

export const profileRepository = createProfileRepository({ get: SecureStore.getItemAsync, set: SecureStore.setItemAsync });

export async function persistProfileAvatar(userId: string, uri: string) {
  const directory = new Directory(Paths.document, 'aegis-profiles', profileNamespace(userId));
  directory.create({ intermediates: true, idempotent: true });
  const source = new File(uri);
  const extension = ['.jpg', '.jpeg', '.png', '.webp', '.heic'].includes(source.extension.toLowerCase()) ? source.extension : '.jpg';
  const destination = new File(directory, `${uuid.v4()}${extension}`);
  await source.copy(destination);
  return destination.uri;
}
