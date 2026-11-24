import '@testing-library/jest-dom/vitest';

// jsdom thay AbortSignal bằng bản riêng, còn Request của Node (undici) từ chối nó khi React Router điều hướng.
// Chỉ ảnh hưởng môi trường test: bỏ `signal` khỏi RequestInit trước khi tạo Request.
const NativeRequest = globalThis.Request;
class TestRequest extends NativeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    if (init?.signal) {
      const { signal, ...rest } = init;
      void signal;
      super(input, rest);
    } else {
      super(input, init);
    }
  }
}
globalThis.Request = TestRequest as typeof Request;
