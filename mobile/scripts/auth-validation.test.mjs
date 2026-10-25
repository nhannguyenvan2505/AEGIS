import assert from 'node:assert/strict';
import test from 'node:test';
import { validateLogin, validateRegister, validateChangePassword } from '../src/features/auth/validation.ts';

const validRegister = { fullName: 'Nguyễn Văn An', email: 'an.nguyen+farm@example.com', password: 'Abcd12345678', confirmPassword: 'Abcd12345678' };
const validChange = { currentPassword: 'current', newPassword: 'Abcd12345678', confirmPassword: 'Abcd12345678' };
const hasErrors = errors => Object.values(errors).some(Boolean);

test('registration requires every field, including whitespace-only values', () => {
  for (const value of ['', '   ']) {
    const errors = validateRegister({ fullName: value, email: value, password: value, confirmPassword: value });
    for (const field of Object.keys(validRegister)) assert.ok(errors[field], field);
  }
});

test('email rejects malformed local parts and domains', () => {
  for (const email of ['farm', 'farm@', '@example.com', 'farm@@example.com', 'farm example@test.com', 'farm@example', 'farm@a..com', '.farm@example.com', 'farm..an@example.com', 'farm@-example.com']) {
    assert.ok(validateRegister({ ...validRegister, email }).email, email);
  }
});

test('email accepts surrounding whitespace, plus addressing and subdomains', () => {
  for (const email of [' an.nguyen+farm@example.com ', 'AN@FARM.EXAMPLE.VN', 'an@my-farm.com']) {
    assert.equal(validateRegister({ ...validRegister, email }).email, undefined);
  }
});

test('registration rejects seven characters and accepts exactly twelve', () => {
  assert.ok(validateRegister({ ...validRegister, password: 'Abcd123', confirmPassword: 'Abcd123' }).password);
  assert.equal(hasErrors(validateRegister(validRegister)), false);
  assert.ok(validateRegister({ ...validRegister, password: '        ', confirmPassword: '        ' }).password);
});

test('registration confirms passwords exactly without trimming or changing case', () => {
  for (const confirmPassword of ['abcd1234', 'Abcd12345678 ', ' Abcd12345678']) {
    assert.ok(validateRegister({ ...validRegister, confirmPassword }).confirmPassword);
  }
  assert.equal(validateRegister({ ...validRegister, password: ' Abcd12345678 ', confirmPassword: ' Abcd12345678 ' }).confirmPassword, undefined);
});

test('login validates required fields and email without assuming a new password policy', () => {
  assert.ok(validateLogin({ email: 'not-an-email', password: ' ' }).email);
  assert.ok(validateLogin({ email: 'an@example.com', password: ' ' }).password);
  assert.equal(hasErrors(validateLogin({ email: 'an@example.com', password: 'short' })), false);
});

test('password change requires all three fields', () => {
  for (const value of ['', '   ']) {
    const errors = validateChangePassword({ currentPassword: value, newPassword: value, confirmPassword: value });
    for (const field of Object.keys(validChange)) assert.ok(errors[field], field);
  }
});

test('password change enforces 12–128 characters on the new password only', () => {
  assert.ok(validateChangePassword({ ...validChange, newPassword: 'Abcd123', confirmPassword: 'Abcd123' }).newPassword);
  assert.equal(hasErrors(validateChangePassword(validChange)), false);
});

test('password change rejects mismatches and revalidates after editing the new password', () => {
  assert.ok(validateChangePassword({ ...validChange, confirmPassword: 'abcd1234' }).confirmPassword);
  assert.ok(validateChangePassword({ ...validChange, newPassword: 'Changed123' }).confirmPassword);
});

test('validation does not mutate credentials', () => {
  const registration = Object.freeze({ ...validRegister, email: ' an@example.com ', password: ' Abcd12345678 ', confirmPassword: ' Abcd12345678 ' });
  const change = Object.freeze({ ...validChange });
  assert.equal(hasErrors(validateRegister(registration)), false);
  assert.equal(hasErrors(validateChangePassword(change)), false);
  assert.equal(registration.password, ' Abcd12345678 ');
  assert.equal(registration.email, ' an@example.com ');
});


test('registration enforces backend password boundaries without trimming', () => {
  for (const size of [11, 129]) assert.ok(validateRegister({ ...validRegister, password: 'x'.repeat(size), confirmPassword: 'x'.repeat(size) }).password);
  for (const size of [12, 128]) assert.equal(hasErrors(validateRegister({ ...validRegister, password: 'x'.repeat(size), confirmPassword: 'x'.repeat(size) })), false);
});
