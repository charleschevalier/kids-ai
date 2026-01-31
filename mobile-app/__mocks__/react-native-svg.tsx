import React from 'react';

const createMockComponent = (name: string) => {
  const Component = (props: any) =>
    React.createElement(name, props, props.children);
  Component.displayName = name;
  return Component;
};

export const Svg = createMockComponent('Svg');
export const Circle = createMockComponent('Circle');
export const Rect = createMockComponent('Rect');
export const Path = createMockComponent('Path');
export const Line = createMockComponent('Line');
export const G = createMockComponent('G');
export const Text = createMockComponent('SvgText');

export default Svg;
