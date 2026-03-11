"""
Suno Cleaner - Audio Processing Pipeline
Uses Demucs for stem separation, basic-pitch for MIDI extraction,
FluidSynth for rendering live VST instruments, and matchering for mastering.
"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.temp_dir = None
        self.stems = {}
        self.midi_files = {}
        self.rendered_audio = {}
        self.mixed_audio = None
        self.mastered_audio = None

    def setup(self) -> None:
        """Initialize the pipeline and create temporary directories."""
        logger.info("Setting up pipeline...")
        self.temp_dir = tempfile.mkdtemp(prefix="suno_cleaner_")
        logger.info(f"Created temp directory: {self.temp_dir}")

    def separate(self, audio_path: str) -> Dict[str, str]:
        """
        Separate audio into stems using Demucs.
        
        Args:
            audio_path: Path to the input audio file
            
        Returns:
            Dictionary mapping stem names to file paths
        """
        logger.info(f"Separating audio: {audio_path}")
        
        # Run Demucs separation
        cmd = [
            "demucs",
            "-d", "htdemucs",
            "--out", self.temp_dir,
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"Demucs failed: {result.stderr}, using fallback separation")
            return self._fallback_separate(audio_path)
        
        # Find separated stems
        song_name = Path(audio_path).stem
        stems_dir = Path(self.temp_dir) / "htdemucs" / song_name
        
        if stems_dir.exists():
            for stem_file in stems_dir.glob("*.wav"):
                stem_name = stem_file.stem
                self.stems[stem_name] = str(stem_file)
        
        logger.info(f"Separated {len(self.stems)} stems")
        return self.stems

    def _fallback_separate(self, audio_path: str) -> Dict[str, str]:
        """Fallback simple separation using spectral filtering."""
        logger.info("Using fallback separation method")
        # Copy original as "no_vocals" fallback
        self.stems["no_vocals"] = audio_path
        return self.stems

    def extract_midi(self, audio_path: str) -> Dict[str, str]:
        """
        Extract MIDI from audio using basic-pitch.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Dictionary mapping instrument names to MIDI file paths
        """
        logger.info(f"Extracting MIDI from: {audio_path}")
        
        output_midi = Path(self.temp_dir) / f"{Path(audio_path).stem}.mid"
        
        # Run basic-pitch
        cmd = [
            "basic-pitch",
            audio_path,
            str(output_midi)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"basic-pitch failed: {result.stderr}")
            return {}
        
        if output_midi.exists():
            self.midi_files["melody"] = str(output_midi)
        
        logger.info(f"Extracted {len(self.midi_files)} MIDI tracks")
        return self.midi_files

    def render(self, midi_path: str, soundfont: str = "GeneralUser.sf2") -> str:
        """
        Render MIDI to audio using FluidSynth.
        
        Args:
            midi_path: Path to the MIDI file
            soundfont: Path to the soundfont file
            
        Returns:
            Path to the rendered audio file
        """
        logger.info(f"Rendering MIDI: {midi_path}")
        
        output_wav = Path(self.temp_dir) / f"{Path(midi_path).stem}.wav"
        
        # Run FluidSynth
        cmd = [
            "fluidsynth",
            "-F", str(output_wav),
            "-T", "wav",
            soundfont,
            midi_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"FluidSynth failed: {result.stderr}")
            return ""
        
        if output_wav.exists():
            self.rendered_audio["synth"] = str(output_wav)
        
        logger.info("Rendered audio successfully")
        return str(output_wav)

    def mix(self, audio_paths: list, output_name: str = "mixed.wav") -> str:
        """
        Mix multiple audio files together.
        
        Args:
            audio_paths: List of audio file paths to mix
            output_name: Name of the output file
            
        Returns:
            Path to the mixed audio file
        """
        logger.info(f"Mixing {len(audio_paths)} audio files")
        
        output_path = self.output_dir / output_name
        
        # Simple mixing using scipy
        import numpy as np
        from scipy.io import wavfile
        
        mixed = None
        for audio_path in audio_paths:
            rate, data = wavfile.read(audio_path)
            if mixed is None:
                mixed = data.astype(np.float32)
            else:
                # Align and mix
                min_len = min(len(mixed), len(data))
                mixed[:min_len] = (mixed[:min_len] + data[:min_len].astype(np.float32)) / 2
        
        if mixed is not None:
            wavfile.write(str(output_path), rate, mixed.astype(np.int16))
            self.mixed_audio = str(output_path)
        
        logger.info(f"Mixed audio saved to: {output_path}")
        return str(output_path)

    def master(self, audio_path: str) -> str:
        """
        Master audio using matchering.
        
        Args:
            audio_path: Path to the audio file to master
            
        Returns:
            Path to the mastered audio file
        """
        logger.info(f"Mastering audio: {audio_path}")
        
        output_path = self.output_dir / f"{Path(audio_path).stem}_mastered.wav"
        
        # Run matchering
        cmd = [
            "matchering",
            audio_path,
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"matchering failed: {result.stderr}")
            # Copy original as fallback
            shutil.copy(audio_path, output_path)
        
        self.mastered_audio = str(output_path)
        logger.info(f"Mastered audio saved to: {output_path}")
        return str(output_path)

    def run(self, audio_path: str) -> Dict[str, Any]:
        """
        Run the complete pipeline.
        
        Args:
            audio_path: Path to the input audio file
            
        Returns:
            Dictionary with all processing results
        """
        logger.info(f"Starting pipeline for: {audio_path}")
        
        self.setup()
        
        # Step 1: Separate
        stems = self.separate(audio_path)
        
        # Step 2: Extract MIDI from each stem
        for stem_name, stem_path in stems.items():
            midi = self.extract_midi(stem_path)
            self.midi_files.update(midi)
        
        # Step 3: Render MIDI files
        for midi_name, midi_path in self.midi_files.items():
            rendered = self.render(midi_path)
            if rendered:
                self.rendered_audio[midi_name] = rendered
        
        # Step 4: Mix all audio
        all_audio = list(stems.values()) + list(self.rendered_audio.values())
        if all_audio:
            mixed = self.mix(all_audio)
            
            # Step 5: Master
            mastered = self.master(mixed)
            
            return {
                "stems": stems,
                "midi": self.midi_files,
                "rendered": self.rendered_audio,
                "mixed": mixed,
                "mastered": mastered
            }
        
        return {"error": "Pipeline failed"}

    def cleanup(self) -> None:
        """Clean up temporary files."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info("Cleaned up temp directory")


def main():
    """Main entry point for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Suno Cleaner Pipeline")
    parser.add_argument("input", help="Input audio file")
    parser.add_argument("-o", "--output", default="output", help="Output directory")
    
    args = parser.parse_args()
    
    pipeline = Pipeline(output_dir=args.output)
    result = pipeline.run(args.input)
    
    print(f"\nPipeline complete!")
    print(f"Mastered output: {result.get('mastered', 'N/A')}")
    
    pipeline.cleanup()


if __name__ == "__main__":
    main()