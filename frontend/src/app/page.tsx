import React from 'react';
import BottomControls from '../components/BottomControls';

const ThreeDScene: React.FC = () => (
  <div className="h-64 bg-gray-200 rounded-lg m-4 flex items-center justify-center">
    <p>3D Scene Placeholder</p>
  </div>
);

const AgentStatusBar: React.FC = () => (
  <div className="h-12 bg-blue-100 flex items-center justify-center">
    <p>Agent Status Bar</p>
  </div>
);

const EventTimeline: React.FC = () => (
  <div className="flex-1 bg-gray-50 p-4 overflow-auto">
    <p>Event Timeline Placeholder</p>
  </div>
);

const HomePage: React.FC = () => {
  return (
    <div className="flex flex-col h-screen">
      <ThreeDScene />
      <AgentStatusBar />
      <EventTimeline />
      <BottomControls />
    </div>
  );
};

export default HomePage;