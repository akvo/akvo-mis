const mockDigestStringAsync = jest.fn();

export const Crypto = {
  CryptoDigestAlgorithm: {
    SHA1: 'SHA1',
  },
  digestStringAsync: mockDigestStringAsync,
  randomUUID: jest.fn(() => 'test-uuid'),
};

export const digestStringAsync = (algorithm, data) => {
  return Promise.resolve(`Mocked${data}-${algorithm}`);
};

export const randomUUID = jest.fn(() => 'test-uuid');

export const CryptoDigestAlgorithm = Crypto.CryptoDigestAlgorithm;
