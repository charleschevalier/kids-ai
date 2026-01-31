import React, {useEffect} from 'react';
import {Path, Circle, Line} from 'react-native-svg';
import Animated, {
  useSharedValue,
  useAnimatedProps,
  withRepeat,
  withSequence,
  withTiming,
  Easing,
  cancelAnimation,
} from 'react-native-reanimated';
import type {SessionState} from '../hooks/useSessionState';

const AnimatedCircle = Animated.createAnimatedComponent(Circle);
const AnimatedPath = Animated.createAnimatedComponent(Path);

type MouthProps = {
  state: SessionState;
};

export function Mouth({state}: MouthProps) {
  const mouthScale = useSharedValue(1);

  useEffect(() => {
    cancelAnimation(mouthScale);

    switch (state) {
      case 'SPEAKING':
        // Rhythmic open/close
        mouthScale.value = withRepeat(
          withSequence(
            withTiming(1.4, {duration: 200, easing: Easing.inOut(Easing.ease)}),
            withTiming(0.6, {duration: 200, easing: Easing.inOut(Easing.ease)}),
          ),
          -1,
          true,
        );
        break;
      default:
        mouthScale.value = withTiming(1, {duration: 200});
        break;
    }
  }, [state, mouthScale]);

  const animatedCircleProps = useAnimatedProps(() => ({
    r: 14 * mouthScale.value,
  }));

  switch (state) {
    case 'DISCONNECTED':
      // Flat line
      return (
        <Line
          x1="165"
          y1="250"
          x2="235"
          y2="250"
          stroke="white"
          strokeWidth="5"
          strokeLinecap="round"
        />
      );

    case 'IDLE':
      // Gentle smile (bezier curve)
      return (
        <Path
          d="M 160 240 Q 200 275 240 240"
          stroke="white"
          strokeWidth="5"
          strokeLinecap="round"
          fill="none"
        />
      );

    case 'LISTENING':
      // Small open circle (attentive)
      return <Circle cx="200" cy="248" r="12" fill="white" />;

    case 'THINKING':
      // Wavy line
      return (
        <Path
          d="M 160 248 Q 175 238 190 248 Q 205 258 220 248 Q 235 238 250 248"
          stroke="white"
          strokeWidth="4"
          strokeLinecap="round"
          fill="none"
        />
      );

    case 'SPEAKING':
      // Animated circle (opens and closes)
      return (
        <AnimatedCircle
          cx="200"
          cy="248"
          animatedProps={animatedCircleProps}
          fill="white"
        />
      );

    default:
      return null;
  }
}
