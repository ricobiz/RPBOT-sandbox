import { useState } from 'react';
import { Button, Slider, Stack, Typography } from '@mui/material';

export default function SceneOverlay() {
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [cameraMode, setCameraMode] = useState<'first' | 'third'>('third');
  const [worldEdit, setWorldEdit] = useState(false);

  return (
    <div style={{ position: 'absolute', top: 16, left: 16, zIndex: 10, background: 'rgba(0,0,0,0.5)', padding: 16, borderRadius: 8 }}>
      <Stack spacing={2} direction="column">
        <Stack direction="row" spacing={1} alignItems="center">
          <Button variant="contained" onClick={() => setPlaying(!playing)}>{playing ? 'Pause' : 'Play'}</Button>
          <Button variant="outlined" onClick={() => setCameraMode(cameraMode === 'first' ? 'third' : 'first')}>Camera: {cameraMode}</Button>
          <Button variant="outlined" onClick={() => setWorldEdit(!worldEdit)}>{worldEdit ? 'Exit Edit' : 'Edit World'}</Button>
        </Stack>
        <Stack spacing={1} direction="column">
          <Typography variant="body2">Time Speed: {speed.toFixed(1)}x</Typography>
          <Slider
            value={speed}
            min={0.1}
            max={5}
            step={0.1}
            onChange={(_, val) => setSpeed(val as number)}
            valueLabelDisplay="auto"
          />
        </Stack>
      </Stack>
    </div>
  );
}
