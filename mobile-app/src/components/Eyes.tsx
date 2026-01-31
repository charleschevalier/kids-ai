import React, {useEffect} from 'react';
import {Circle, Line, G} from 'react-native-svg';
import Animated, {
  useSharedValue,
  useAnimatedProps,
  withRepeat,
  withSequence,
  withTiming,
  withDelay,
  Easing,
  cancelAnimation,
} from 'react-native-reanimated';
import type {SessionState} from '../hooks/useSessionState';

const AnimatedCircle = Animated.createAnimatedComponent(Circle);
const AnimatedG = Animated.createAnimatedComponent(G);

type EyesProps = {
  state: SessionState;
};

export function Eyes({state}: EyesProps) {
  const scaleY = useSharedValue(1);
  const translateX = useSharedValue(0);

  useEffect(() => {
    cancelAnimation(scaleY);
    cancelAnimation(translateX);

    switch (state) {
      case 'IDLE':
        // Slow blink every 3 seconds
        translateX.value = withTiming(0, {duration: 200});
        scaleY.value = withRepeat(
          withDelay(
            3000,
            withSequence(
              withTiming(0.1, {duration: 120, easing: Easing.inOut(Easing.ease)}),
              withTiming(1, {duration: 120, easing: Easing.inOut(Easing.ease)}),
            ),
          ),
          -1,
        );
        break;

      case 'LISTENING':
        // Wide open, no blink
        translateX.value = withTiming(0, {duration: 200});
        scaleY.value = withTiming(1.15, {duration: 300});
        break;

      case 'THINKING':
        // Look around
        scaleY.value = withTiming(0.85, {duration: 300});
        translateX.value = withRepeat(
          withSequence(
            withTiming(12, {duration: 800, easing: Easing.inOut(Easing.ease)}),
            withTiming(-12, {duration: 800, easing: Easing.inOut(Easing.ease)}),
          ),
          -1,
          true,
        );
        break;

      case 'SPEAKING':
        // Happy squint
        translateX.value = withTiming(0, {duration: 200});
        scaleY.value = withTiming(0.7, {duration: 300});
        break;

      case 'DISCONNECTED':
      default:
        translateX.value = withTiming(0, {duration: 200});
        scaleY.value = withTiming(1, {duration: 200});
        break;
    }
  }, [state, scaleY, translateX]);

  const leftEyeProps = useAnimatedProps(() => ({
    cy: 155,
    scaleY: scaleY.value,
    translateX: translateX.value,
  }));

  const rightEyeProps = useAnimatedProps(() => ({
    cy: 155,
    scaleY: scaleY.value,
    translateX: translateX.value,
  }));

  if (state === 'DISCONNECTED') {
    // X-shaped eyes
    return (
      <G>
        {/* Left X */}
        <Line x1="130" y1="140" x2="160" y2="170" stroke="white" strokeWidth="6" strokeLinecap="round" />
        <Line x1="160" y1="140" x2="130" y2="170" stroke="white" strokeWidth="6" strokeLinecap="round" />
        {/* Right X */}
        <Line x1="240" y1="140" x2="270" y2="170" stroke="white" strokeWidth="6" strokeLinecap="round" />
        <Line x1="270" y1="140" x2="240" y2="170" stroke="white" strokeWidth="6" strokeLinecap="round" />
      </G>
    );
  }

  return (
    <AnimatedG animatedProps={{translateX: leftEyeProps.translateX}}>
      <AnimatedCircle
        cx="145"
        animatedProps={leftEyeProps}
        r="22"
        fill="white"
        scaleY={leftEyeProps.scaleY}
      />
      <AnimatedCircle
        cx="255"
        animatedProps={rightEyeProps}
        r="22"
        fill="white"
        scaleY={rightEyeProps.scaleY}
      />
    </AnimatedG>
  );
}
