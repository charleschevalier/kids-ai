// Minimal reanimated mock for testing
const React = require('react');

const useSharedValue = (initial: any) => {
  const ref = React.useRef({value: initial});
  return ref.current;
};
const useAnimatedStyle = (fn: () => any) => fn();
const useAnimatedProps = (fn: () => any) => fn();
const useDerivedValue = (fn: () => any) => ({value: fn()});

const withTiming = (value: any) => value;
const withSpring = (value: any) => value;
const withRepeat = (value: any) => value;
const withSequence = (...values: any[]) => values[values.length - 1];
const withDelay = (_delay: number, value: any) => value;
const cancelAnimation = () => {};
const interpolateColor = (
  _value: number,
  _inputRange: number[],
  outputRange: string[],
) => outputRange[0];

const Easing = {
  ease: (t: number) => t,
  linear: (t: number) => t,
  inOut: (fn: any) => fn,
  in: (fn: any) => fn,
  out: (fn: any) => fn,
};

const Animated = {
  View: 'Animated.View',
  Text: 'Animated.Text',
  createAnimatedComponent: (Component: any) => Component,
};

export default {
  ...Animated,
  useSharedValue,
  useAnimatedStyle,
  useAnimatedProps,
  useDerivedValue,
  withTiming,
  withSpring,
  withRepeat,
  withSequence,
  withDelay,
  cancelAnimation,
  interpolateColor,
  Easing,
  createAnimatedComponent: (Component: any) => Component,
};

export {
  useSharedValue,
  useAnimatedStyle,
  useAnimatedProps,
  useDerivedValue,
  withTiming,
  withSpring,
  withRepeat,
  withSequence,
  withDelay,
  cancelAnimation,
  interpolateColor,
  Easing,
};
