'use client';

import { 
  RoomAudioRenderer, 
  StartAudio, 
  useConnectionState,
  useDataChannel,
  useRoomContext
} from '@livekit/components-react';
import { ConnectionState } from 'livekit-client';
import type { AppConfig } from '@/app-config';
import { SessionProvider } from '@/components/app/session-provider';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/livekit/toaster';
import { useState } from 'react';

interface AppProps {
  appConfig: AppConfig;
}

// --- 1. Game State Hook (Retained for agent logic only, no visual display) ---
const useGameState = () => {
  const [state, setState] = useState({
    player: {
      hp: 100,
      max_hp: 100,
      ram: 80,
      max_ram: 100,
      status: "Healthy",
      inventory: ["Data Spike", "Silenced Pistol", "Burner Phone"]
    },
    world: {
      location: "Neo-Kyoto Rooftops",
      danger_level: "Medium"
    },
    log: [] as string[]
  });

  const room = useRoomContext();

  useDataChannel((payload, participant, topic) => {
    // @ts-ignore
    const rawPayload = payload?.payload ?? payload; 
    if (!rawPayload) return;
    const text = new TextDecoder().decode(rawPayload);
    try {
      const data = JSON.parse(text);
      if (topic === "game_state_update") {
        setState(data);
      } 
    } catch (e) { console.error("Data Packet Error:", e); }
  });

  return { state, room };
};

// --- 2. Visual Components ---

const CRTOverlay = () => (
  <div className="pointer-events-none absolute inset-0 z-40 overflow-hidden h-full w-full">
    {/* Scanlines and Glitch lines */}
    <div className="absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.4)_50%),linear-gradient(90deg,rgba(255,0,0,0.1),rgba(0,0,0,0.05),rgba(255,255,0,0.1))] z-50 bg-[length:100%_2px,3px_100%] pointer-events-none opacity-40" />
  </div>
);

// --- 4. Header (Static and Simplified) ---
const CyberHeader = () => {
  const state = useConnectionState();
  return (
    <header className="border-b border-red-900/50 bg-black/90 p-4 px-6 flex justify-between items-center text-red-500 font-mono shadow-lg relative z-[100]">
      <div className="flex items-center gap-3">
          {/* Status dot is static */}
          <div className={`w-3 h-3 rounded-full ${state === ConnectionState.Connected ? 'bg-red-500' : 'bg-red-900'}`}></div>
          <div className="text-2xl font-black tracking-[0.2em] text-red-400 drop-shadow-[0_0_10px_rgba(255,0,0,0.8)]">
            CYBERPUNK
          </div>
      </div>
      <div className="flex items-center gap-4 text-xs border border-red-900/50 px-3 py-1 rounded bg-red-950/20">
          <span className="opacity-50 text-red-700">SIGNAL:</span>
          <span className={`${state === ConnectionState.Connected ? 'text-yellow-400' : 'text-red-500'} font-bold tracking-wider`}>
            {state === ConnectionState.Connected ? 'GLITCHED_COMM' : `${state}`.toUpperCase()}
          </span>
      </div>
    </header>
  );
};

// --- 5. Main Dashboard (Only Video Feed) ---
const GameDashboard = () => {
  const { room } = useGameState();

  return (
    <div className="flex flex-col h-full w-full absolute inset-0 z-10 pointer-events-auto">
      <CyberHeader />
      
      {/* Centered Main Content */}
      <div className="flex flex-1 overflow-hidden relative justify-center items-center p-4 md:p-8">

        {/* Center Container for GM Stream (Primary Focus) */}
        <div className="flex flex-col w-full max-w-4xl h-full justify-center items-center">
             
             {/* GM_AUDIO_STREAM (The Operator's Visual Feed) */}
             <div className="w-full h-full max-h-[80vh] border border-red-700/50 bg-black rounded-lg relative overflow-hidden shadow-[0_0_30px_rgba(255,0,0,0.3)] flex-shrink-0">
                 
                 {/* Centered Error Text (UPDATED) */}
                 <div className="absolute inset-0 flex flex-col justify-center items-center pointer-events-none z-30">
                    <div className="text-xl font-black tracking-widest text-red-500/80 drop-shadow-lg">ERROR [404] CORE_FEED_NOT_FOUND</div>
                    <div className="text-sm font-mono text-yellow-400/80 mt-2">!! SYSTEM FAILURE !!</div> 
                 </div>

                 <ViewController />
             </div>
             
        </div>
      </div>
      
      {/* Mobile Fab position */}
      <div className="lg:hidden absolute bottom-8 right-4 w-32 h-32 z-50 border border-red-500/50 rounded-full overflow-hidden bg-black/90 shadow-[0_0_20px_rgba(255,0,0,0.3)]">
        <ViewController />
      </div>
    </div>
  );
};

export function App({ appConfig }: AppProps) {
  return (
    <SessionProvider appConfig={appConfig}>
      {/* Root Container */}
      <div className="relative h-svh w-full overflow-hidden bg-black">
        
        {/* BROKEN SYSTEM BACKGROUND */}
        
        {/* 1. Black Base */}
        <div className="absolute inset-0 bg-black"></div> 
        
        {/* 2. Increased Glitch Grid (Red lines, tighter spacing) */}
        <div className="absolute inset-0 opacity-20 bg-[size:2px_2px] bg-repeat [background-image:linear-gradient(to_right,#FF0000_1px,transparent_1px),linear-gradient(to_bottom,#FF0000_1px,transparent_1px)]"></div>
        
        {/* 3. Spark/Digital Grit Layer (Dense, subtle dots) */}
        <div className="absolute inset-0 opacity-20 bg-[size:1px_1px] bg-repeat [background-image:radial-gradient(red_30%,transparent_0)]"></div>
        
        {/* 4. Broken/Fragmented Areas (Simulating a smashed screen or corrupted data blocks) */}
        <div className="absolute inset-0 opacity-10 bg-[size:100px_100px] bg-repeat [background-image:repeating-linear-gradient(45deg,#000000_0,#000000_20px,#FF0000_20px,#FF0000_40px)] mix-blend-color-dodge" style={{ clipPath: 'polygon(10% 20%, 30% 15%, 45% 40%, 25% 45%)' }}></div>
        <div className="absolute inset-0 opacity-15 bg-[size:70px_70px] bg-repeat [background-image:repeating-linear-gradient(-45deg,#000000_0,#000000_10px,#FFA500_10px,#FFA500_20px)] mix-blend-difference" style={{ clipPath: 'polygon(60% 70%, 85% 65%, 90% 80%, 65% 85%)' }}></div>
        
        {/* 7. DARKER GREEN HALF-SCREEN OVERLAY (UPDATED BLEND MODE) */}
        <div 
          className="absolute inset-0 pointer-events-none z-10" 
          style={{
            // Darker Green on the left (0% to 49%), quickly fading to transparent (50% to 100%)
            background: 'linear-gradient(90deg, #004d00 0%, #002600 48%, transparent 50%, transparent 100%)',
            mixBlendMode: 'color-burn', // 'color-burn' or 'hard-light' creates a darker, corrupted look
          }}
        />

        {/* 5. Short Circuit Flash (Electric Arc) */}
        <div className="absolute inset-x-0 h-0.5 top-[40%] bg-gradient-to-r from-red-500 via-yellow-300 to-red-500 shadow-[0_0_15px_rgba(255,255,0,0.8)] opacity-70 pointer-events-none z-20" />
        
        {/* 6. Error Lighting */}
        <div className="absolute inset-0 pointer-events-none" style={{
            boxShadow: 'inset 0 0 100px rgba(255,0,0,0.1), 0 0 150px rgba(255,165,0,0.1)',
            background: 'radial-gradient(circle at 10% 10%, rgba(255,0,0,0.1) 0%, transparent 60%)'
        }}></div>
        
        <CRTOverlay />
        <GameDashboard />
        
      </div>

      <StartAudio label=">>> INITIATE CONNECTION" /> 
      <RoomAudioRenderer />
      <Toaster />
    </SessionProvider>
  );
}