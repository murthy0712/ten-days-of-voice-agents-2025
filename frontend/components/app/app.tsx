'use client';

import { RoomAudioRenderer, StartAudio } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { SessionProvider } from '@/components/app/session-provider';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/livekit/toaster';
import { cn } from '@/lib/utils';

interface AppProps {
    appConfig: AppConfig;
}

// === CRICKET THEME EMOJIS ===
const EmojiBall = () => <span className="text-[1.5em] md:text-[2em]">🏏</span>; 
const EmojiTrophy = () => <span className="text-[1.5em] md:text-[2em]">🏆</span>; 

// === STATIC ICON COMPONENT (MODIFIED) ===
interface StaticIconProps {
    children: React.ReactNode;
    size: string;
    // Removed position property, using top/left style props directly
    top: number; 
    left: number; 
    rotate: number; 
}

const StaticIcon = ({ children, size, top, left, rotate }: StaticIconProps) => (
    <div
        className={cn(
            // --- CRITICAL FIX: Z-index and Opacity ---
            "absolute opacity-[0.4] pointer-events-none select-none transition-none z-0",
            size,
            // Rotation is now applied via dynamic style
            // text-lime-400/50 is reapplied for visual consistency across backgrounds
            "text-lime-400/50" 
        )}
        style={{
            // --- CRITICAL FIX: Inline Style for Positioning ---
            top: `${top}%`,
            left: `${left}%`,
            transform: `rotate(${rotate}deg)`, // Apply rotation via inline style
        }}
    >
        {children}
    </div>
);


// === FUNCTION TO GENERATE RANDOM ICONS (MODIFIED) ===
const generateRandomIcons = (count: number) => {
    const icons = [];
    
    for (let i = 0; i < count; i++) {
        // Generate raw numeric values for positioning and rotation
        const top = Math.random() * 100;
        const left = Math.random() * 100;
        const rotate = Math.floor(Math.random() * 90) - 45;

        const sizeOptions = [8, 10, 12, 14, 16, 20];
        const randomSize = sizeOptions[Math.floor(Math.random() * sizeOptions.length)];
        
        const IconComponent = i % 2 === 0 ? EmojiTrophy : EmojiBall;

        icons.push(
            <StaticIcon 
                key={i}
                // Pass raw numbers to StaticIcon
                top={top}
                left={left}
                rotate={rotate}
                size={`w-${randomSize} h-${randomSize}`}
            >
                <IconComponent />
            </StaticIcon>
        );
    }
    return icons;
};

// Generate icons once (150 is a good visible density)
const backgroundIcons = generateRandomIcons(150);


export function App({ appConfig }: AppProps) {
    return (
        <div className="relative h-svh w-full bg-gradient-to-t from-black to-green-950 text-white overflow-hidden">
            
            {/* Background Static Cricket Emojis */}
            {backgroundIcons}
            
            <SessionProvider appConfig={appConfig}>
                <main className="grid h-svh grid-cols-1 place-content-center relative z-10">
                    <ViewController />
                </main>
                <StartAudio label="Ready for the First Ball" />
                <RoomAudioRenderer />
                <Toaster />
            </SessionProvider>
        </div>
    );
}
