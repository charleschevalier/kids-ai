import React from 'react';
import {StatusBar} from 'react-native';
import {VoiceSession} from './src/components/VoiceSession';
import {RobotFace} from './src/components/RobotFace';

export default function App() {
  return (
    <>
      <StatusBar hidden />
      <VoiceSession>
        <RobotFace />
      </VoiceSession>
    </>
  );
}
