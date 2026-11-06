const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Limit workers only for the native emulator build on this development machine.
if (process.env.AEGIS_LOW_MEMORY_BUILD === '1') {
  config.maxWorkers = 1;
}

module.exports = config;
