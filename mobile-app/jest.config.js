module.exports = {
  preset: 'react-native',
  transformIgnorePatterns: [
    'node_modules/(?!(react-native|@react-native|react-native-audio-api|react-native-safe-area-context)/)',
  ],
};
