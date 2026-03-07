import React, { useState } from 'react';

const BottomControls: React.FC = () => {
  const [panel, setPanel] = useState<string | null>(null);
  const [message, setMessage] = useState('');

  const openPanel = (name: string) => setPanel(name);
  const closePanel = () => setPanel(null);

  return (
    <div className="fixed bottom-0 w-full bg-white shadow-md">
      <div className="flex items-center p-2 border-t">
        <input
          type="text"
          placeholder="Chat with agent..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className="flex-1 border rounded px-2 py-1"
        />
        <button
          onClick={() => alert(`Sending: ${message}`)}
          className="ml-2 bg-blue-500 text-white px-3 py-1 rounded"
        >
          Send
        </button>
      </div>
      <div className="flex justify-around p-2 border-t">
        <button onClick={() => openPanel('addObject')} className="text-sm">
          Add Object
        </button>
        <button onClick={() => openPanel('addObstacle')} className="text-sm">
          Add Obstacle
        </button>
        <button onClick={() => openPanel('changeRule')} className="text-sm">
          Change Rule
        </button>
        <button onClick={() => openPanel('assignTask')} className="text-sm">
          Assign Task
        </button>
      </div>

      {/* Bottom sheet panels */}
      {panel && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-end"
          onClick={closePanel}
        >
          <div
            className="bg-white w-full rounded-t-lg p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold mb-2">
              {panel.replace(/([A-Z])/g, ' $1').trim()}
            </h3>
            <p>Panel content for {panel} goes here.</p>
            <button
              onClick={closePanel}
              className="mt-4 bg-gray-200 px-3 py-1 rounded"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default BottomControls;