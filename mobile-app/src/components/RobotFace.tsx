import React, {useEffect} from 'react';
import {StyleSheet, Text, View} from 'react-native';
import Svg from 'react-native-svg';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  interpolateColor,
} from 'react-native-reanimated';
import {useSession} from './VoiceSession';
import {Eyes} from './Eyes';
import {Mouth} from './Mouth';
import type {SessionState} from '../hooks/useSessionState';

const STATE_COLORS: Record<SessionState, string> = {
  DISCONNECTED: '#616161',
  IDLE: '#4A90D9',
  LISTENING: '#4CAF50',
  THINKING: '#FFA726',
  SPEAKING: '#AB47BC',
};

const STATE_INDEX: Record<SessionState, number> = {
  DISCONNECTED: 0,
  IDLE: 1,
  LISTENING: 2,
  THINKING: 3,
  SPEAKING: 4,
};

const COLOR_OUTPUT_RANGE = [
  STATE_COLORS.DISCONNECTED,
  STATE_COLORS.IDLE,
  STATE_COLORS.LISTENING,
  STATE_COLORS.THINKING,
  STATE_COLORS.SPEAKING,
];

export function RobotFace() {
  const {state, error} = useSession();
  const stateIndex = useSharedValue(STATE_INDEX.DISCONNECTED);

  useEffect(() => {
    stateIndex.value = withTiming(STATE_INDEX[state], {duration: 400});
  }, [state, stateIndex]);

  const animatedStyle = useAnimatedStyle(() => ({
    backgroundColor: interpolateColor(
      stateIndex.value,
      [0, 1, 2, 3, 4],
      COLOR_OUTPUT_RANGE,
    ),
  }));

  return (
    <Animated.View style={[styles.container, animatedStyle]}>
      <Svg viewBox="0 0 400 400" style={styles.face}>
        <Eyes state={state} />
        <Mouth state={state} />
      </Svg>
      {state === 'DISCONNECTED' && (
        <Text style={styles.statusText}>Connecting...</Text>
      )}
      {error && <Text style={styles.errorText}>{error}</Text>}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  face: {
    width: '80%',
    aspectRatio: 1,
  },
  statusText: {
    position: 'absolute',
    bottom: 60,
    color: 'rgba(255, 255, 255, 0.7)',
    fontSize: 18,
    fontWeight: '300',
  },
  errorText: {
    position: 'absolute',
    bottom: 30,
    color: 'rgba(255, 100, 100, 0.9)',
    fontSize: 14,
  },
});
