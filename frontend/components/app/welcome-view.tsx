import React, { useState } from 'react';
import { Button } from '@/components/livekit/button';

/**
 * Cricket Bat & Ball SVG Icon (Replacing WelcomeImage)
 */
function CricketIcon() {
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="text-yellow-400 mb-6 size-20 drop-shadow-[0_0_15px_rgba(252,211,77,0.5)] z-10 relative"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      {/* Cricket Bat */}
      <path
        d="M6 3L11 8M11 8L16 3M11 8V21M11 21H13M11 21H9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Cricket Ball */}
      <circle cx="18" cy="18" r="3" fill="red" stroke="white" strokeWidth="1" />
      <path
        d="M18 15V21"
        stroke="white"
        strokeWidth="1"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * Helmet Icon (Replacing RetroTvIcon)
 */
function HelmetIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path
        d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M12 19C15.866 19 19 15.866 19 12M12 19C8.13401 19 5 15.866 5 12"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M12 2C10.5 5 8 9 5 12"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M12 2C13.5 5 16 9 19 12"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export const WelcomeView = React.forwardRef<HTMLDivElement, any>(
  ({ startButtonText, onStartCall }, ref) => {
    const [name, setName] = useState('');
    const [started, setStarted] = useState(false);

    async function handleStart() {
      if (name.trim().length > 0) {
        setStarted(true);
        onStartCall?.(name.trim());
      }
    }

    return (
      <div
        ref={ref}
        className="min-h-screen w-full flex flex-col justify-center 
        items-center 
        bg-transparent text-white" // CHANGED: Replaced items-end and padding classes with just items-center
      >
        {!started && (
          <section className="relative flex flex-col items-center text-center p-8 
          bg-[#1a1a1a] rounded-3xl overflow-hidden
          /* Updated Shadow for Cricket: Green Glow + Deep Shadows */
          shadow-[0_0_50px_rgba(34,197,94,0.4),12px_12px_24px_#0d0d0d,-12px_-12px_24px_#272727]
          border border-white/10
          w-full max-w-sm mx-4 md:mx-0">
            
            {/* === DECORATIVE ICONS & EMOJIS (Cricket-themed) === */}
            <HelmetIcon className="absolute top-4 right-4 w-10 h-10 text-green-500 -rotate-12 pointer-events-none drop-shadow-[0_0_8px_rgba(34,197,94,0.6)] opacity-90" />
            <HelmetIcon className="absolute bottom-16 left-2 w-8 h-8 text-white rotate-6 pointer-events-none opacity-50" />
            
            <div className="absolute top-10 left-6 text-3xl opacity-90 rotate-[-15deg] pointer-events-none select-none drop-shadow-[0_0_12px_rgba(255,0,0,0.5)]">
              🏏
            </div>
            <div className="absolute bottom-4 right-6 text-2xl opacity-90 rotate-[10deg] pointer-events-none select-none drop-shadow-[0_0_12px_rgba(255,255,0,0.5)]">
              🏆
            </div>
            <div className="absolute top-1/2 left-2 text-xl opacity-90 -rotate-[20deg] pointer-events-none select-none drop-shadow-[0_0_12px_rgba(59,130,246,0.5)]">
              🏟️
            </div>

            <CricketIcon />

            <h2 className="text-2xl font-bold text-white mb-2 drop-shadow-md tracking-tight z-10 relative">
              Ready to take the crease?
            </h2>
            <p className="max-w-prose leading-6 font-medium text-white/80 z-10 relative">
              Enter your player name and let's start the match!
            </p>

            <div className="mt-8 w-full z-10 relative">
              <label className="block text-xs font-bold uppercase tracking-wider mb-2 text-left text-white/60 ml-1">
                Your Player Name
              </label>
              
              {/* INPUT AND BUTTON ROW */}
              <div className="flex w-full items-stretch gap-2">
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleStart();
                  }}
                  placeholder="Player ID..."
                  className="flex-1 rounded-xl border-none px-4 py-3 
                  bg-[#1a1a1a] text-white placeholder:text-white/40 font-semibold
                  shadow-[inset_4px_4px_8px_#0d0d0d,inset_-4px_-4px_8px_#272727]
                  focus:outline-none focus:ring-2 focus:ring-green-400/50
                  transition-all duration-200"
                />

                <Button
                  variant="primary"
                  size="default"
                  onClick={handleStart}
                  disabled={name.trim().length === 0}
                  className="px-6 rounded-xl font-bold uppercase
                  /* Button Gradient: Green to Blue */
                  bg-gradient-to-r from-green-500 to-blue-600 
                  text-white border-none
                  hover:from-green-400 hover:to-blue-500
                  shadow-lg transform hover:scale-[1.03] transition-all flex items-center justify-center"
                >
                  {/* Play Icon (Replacing Arrow) */}
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="size-6">
                    <path fillRule="evenodd" d="M4.5 5.653c0-1.427 1.529-2.33 2.779-1.643l11.54 6.416c1.249.693 1.25 2.513 0 3.206l-11.54 6.416c-1.25.687-2.779-.217-2.779-1.643V5.653Z" clipRule="evenodd" />
                  </svg>
                </Button>
              </div>
            </div>

            <div className="mt-4 text-[10px] text-white/40 font-mono uppercase tracking-widest z-10 relative">
              Press Enter to Bat
            </div>
          </section>
        )}

        {started && (
          <div className="text-center text-white text-2xl font-bold animate-pulse drop-shadow-lg">
            🏏 Umpire is calling... Play!
          </div> // CHANGED: Removed unnecessary md:pr-12
        )}
      </div>
    );
  }
);

WelcomeView.displayName = 'WelcomeView';
