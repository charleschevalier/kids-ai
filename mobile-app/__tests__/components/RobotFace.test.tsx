import React from 'react';
import {render} from '@testing-library/react-native';
import {RobotFace} from '../../src/components/RobotFace';
import type {SessionState} from '../../src/hooks/useSessionState';

jest.mock('react-native-audio-api');
jest.mock('react-native-reanimated');
jest.mock('react-native-svg');

// Mock the VoiceSession context
const mockSessionState: {state: SessionState; transcripts: any[]; error: string | null} = {
  state: 'DISCONNECTED',
  transcripts: [],
  error: null,
};

jest.mock('../../src/components/VoiceSession', () => ({
  useSession: () => mockSessionState,
}));

describe('RobotFace', () => {
  const states: SessionState[] = [
    'DISCONNECTED',
    'IDLE',
    'LISTENING',
    'THINKING',
    'SPEAKING',
  ];

  for (const state of states) {
    it(`renders without crashing for ${state} state`, () => {
      mockSessionState.state = state;
      mockSessionState.error = null;
      const {toJSON} = render(<RobotFace />);
      expect(toJSON()).not.toBeNull();
    });
  }

  it('shows "Connecting..." text when DISCONNECTED', () => {
    mockSessionState.state = 'DISCONNECTED';
    mockSessionState.error = null;
    const {getByText} = render(<RobotFace />);
    expect(getByText('Connecting...')).toBeTruthy();
  });

  it('does not show "Connecting..." text when IDLE', () => {
    mockSessionState.state = 'IDLE';
    mockSessionState.error = null;
    const {queryByText} = render(<RobotFace />);
    expect(queryByText('Connecting...')).toBeNull();
  });

  it('shows error text when error is set', () => {
    mockSessionState.state = 'IDLE';
    mockSessionState.error = 'Connection lost';
    const {getByText} = render(<RobotFace />);
    expect(getByText('Connection lost')).toBeTruthy();
  });

  it('does not show error text when error is null', () => {
    mockSessionState.state = 'IDLE';
    mockSessionState.error = null;
    const {queryByText} = render(<RobotFace />);
    expect(queryByText('Connection lost')).toBeNull();
  });
});
