import assert from 'node:assert/strict';
import test from 'node:test';
import { moduleUrl } from './load-followup-test.mjs';

const { normalizeProfile, validateProfile, profileKey, profileInitial, profilePhone, createProfileRepository } =
  await import(await moduleUrl(new URL('../src/features/profile/profileModel.ts', import.meta.url)));
const valid = { fullName: 'Nguyễn Văn Minh', email: 'minh@example.com', phone: '0912345678', avatarUri: null };
function storage() {
  const records = new Map();
  return { records, get: async key => records.get(key) ?? null, set: async (key, value) => { records.set(key, value); } };
}

test('profile normalizes Vietnamese names and formatted phone numbers without mutating the input', () => {
  const input = { fullName: '  Nguyễn   Văn Minh  ', email: ' minh@example.com ', phone: '0912 345-678' };
  const original = structuredClone(input);
  assert.deepEqual(normalizeProfile(input), { fullName: valid.fullName, email: valid.email, phone: valid.phone });
  assert.deepEqual(validateProfile(input), {});
  assert.deepEqual(input, original);
  assert.equal(profileInitial(valid), 'M');
  assert.equal(profilePhone(valid.phone), '0912 345 678');
  assert.equal(profilePhone(''), 'Chưa cập nhật');
});

test('invalid required fields return separate errors and accept a valid ten digit Vietnamese phone', () => {
  const errors = validateProfile({ fullName: '  ', email: 'minh@', phone: '0912 345' });
  assert.deepEqual(Object.keys(errors).sort(), ['email', 'fullName', 'phone']);
  for (const phone of ['1912345678', '+84912345678', '09123456789', '09123abc78']) assert.ok(validateProfile({ ...valid, phone }).phone);
  for (const email of ['a..b@example.com', 'minh@', '@example.com', 'minh@example', 'a'.repeat(255) + '@example.com']) assert.ok(validateProfile({ ...valid, email }).email);
  assert.ok(validateProfile({ ...valid, fullName: 'a'.repeat(121) }).fullName);
  assert.deepEqual(validateProfile(valid), {});
});

test('saved profiles survive a new repository and stay separated by authenticated owner', async () => {
  const disk = storage();
  const repository = createProfileRepository(disk);
  const initial = await repository.read('owner-a', valid.email);
  assert.equal(initial.email, valid.email);
  assert.equal(initial.fullName, '');
  const saved = await repository.save('owner-a', { ...valid, avatarUri: 'file:///app/profile/avatar.jpg' }, valid.email);
  assert.deepEqual(await createProfileRepository(disk).read('owner-a', valid.email), saved);
  assert.deepEqual(await repository.read('owner-b', 'other@example.com'), { fullName: '', phone: '', email: 'other@example.com', avatarUri: null });
  assert.notEqual(profileKey('a/b'), profileKey('a_2fb'));
  assert.match(profileKey('người/dùng'), /^[a-z0-9.-]+$/);
  assert.equal(initial.email, valid.email);
});

test('invalid edits, changed owner metadata and unsupported avatar locations never overwrite a valid profile', async () => {
  const disk = storage();
  const repository = createProfileRepository(disk);
  await repository.save('owner-a', valid, valid.email);
  const original = disk.records.get(profileKey('owner-a'));
  for (const changes of [{ phone: '123' }, { email: 'invalid' }, { avatarUri: 'https://external.test/photo.jpg' }]) {
    await assert.rejects(repository.save('owner-a', { ...valid, ...changes }, valid.email));
    assert.equal(disk.records.get(profileKey('owner-a')), original);
  }
  disk.records.set(profileKey('owner-b'), original);
  await assert.rejects(repository.read('owner-b', 'other@example.com'));
  disk.records.set(profileKey('owner-a'), '{broken');
  await assert.rejects(repository.read('owner-a', 'login@example.com'));
});

test('storage failures reject saving and retain the previously saved profile', async () => {
  const disk = storage();
  const repository = createProfileRepository(disk);
  await repository.save('owner-a', valid, valid.email);
  const unavailable = createProfileRepository({ ...disk, set: async () => { throw new Error('Storage unavailable'); } });
  await assert.rejects(unavailable.save('owner-a', { ...valid, fullName: 'Tên mới' }, valid.email), /Storage unavailable/);
  assert.deepEqual(await repository.read('owner-a', valid.email), valid);
});

test('profile edits cannot change login email, and old contact email overrides are ignored', async () => {
  const disk = storage();
  const repository = createProfileRepository(disk);
  await repository.save('owner-a', valid, valid.email);
  const original = disk.records.get(profileKey('owner-a'));
  await assert.rejects(repository.save('owner-a', { ...valid, email: 'other@example.com' }, valid.email), /Email đăng nhập không thể thay đổi/);
  assert.equal(disk.records.get(profileKey('owner-a')), original);
  disk.records.set(profileKey('owner-a'), JSON.stringify({ version: 1, owner: 'owner-a', profile: { ...valid, email: 'old-contact@example.com' } }));
  const restored = await repository.read('owner-a', valid.email);
  assert.equal(restored.email, valid.email);
  assert.equal(restored.fullName, valid.fullName);
  assert.equal(restored.phone, valid.phone);
});
