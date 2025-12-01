'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { useLocalParticipant } from '@livekit/components-react';
import { ParticipantEvent, type LocalParticipant } from 'livekit-client';
import type { AppConfig } from '@/app-config';
import { ChatTranscript } from '@/components/app/chat-transcript';
import { PreConnectMessage } from '@/components/app/preconnect-message';
import { TileLayout } from '@/components/app/tile-layout';
import {
    AgentControlBar,
    type ControlBarControls,
} from '@/components/livekit/agent-control-bar/agent-control-bar';
import { useChatMessages } from '@/hooks/useChatMessages';
import { useConnectionTimeout } from '@/hooks/useConnectionTimout';
import { useDebugMode } from '@/hooks/useDebug';
import { cn } from '@/lib/utils';
import { ScrollArea } from '../livekit/scroll-area/scroll-area';

const MotionBottom = motion.create('div');

const IN_DEVELOPMENT = process.env.NODE_ENV !== 'production';
const BOTTOM_VIEW_MOTION_PROPS = {
    variants: {
        visible: {
            opacity: 1,
            translateY: '0%',
        },
        hidden: {
            opacity: 0,
            translateY: '100%',
        },
    },
    initial: 'hidden',
    animate: 'visible',
    exit: 'hidden',
    transition: {
        duration: 0.3,
        delay: 0.5,
        ease: 'easeOut',
    },
};

interface FadeProps {
    top?: boolean;
    bottom?: boolean;
    className?: string;
}

export function Fade({ top = false, bottom = false, className }: FadeProps) {
    return (
        <div
            className={cn(
                'pointer-events-none h-4',
                top && 'bg-gradient-to-b from-black/10 to-transparent',
                bottom && 'bg-gradient-to-t from-black/10 to-transparent',
                className
            )}
        />
    );
}

// === CRICKET THEME BACKGROUND ICONS ===
// These icons are kept but their usage is replaced by the simpler stadium lights gradient.
const CricketBallIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-2-12h4v2h-4v-2zm0 4h4v2h-4v-2zm0 4h4v2h-4v-2z" />
    </svg>
);

const WicketIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full">
        <path d="M12 2L6 22h12L12 2zm0 3.82L15.32 17H8.68L12 3.82zM12 2l-6 20h12L12 2zm0 3.82L15.32 17H8.68L12 3.82z" />
    </svg>
);

const BatIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full">
        <path d="M13 1.07V9h4.94l-2.01 4.5 2.01 4.5H13v3.93c4.95-.5 8-5.35 8-10.93s-3.05-10.43-8-10.93zM11 1.07c-4.95.5-8 5.35-8 10.93s3.05 10.43 8 10.93V15h-4.94l2.01-4.5-2.01-4.5H11V1.07z" />
    </svg>
);


const FloatingIcon = ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={cn("absolute opacity-10 text-lime-400/50 pointer-events-none select-none", className)}>
        {children}
    </div>
);

// === PLAYER BADGE - Cricket Themed & Centered ===
function PlayerBadge({ participant }: { participant?: LocalParticipant }) {
    const [displayName, setDisplayName] = useState('Player');

    useEffect(() => {
        if (!participant) return;

        const updateName = () => {
            let name = participant.name || '';

            if ((!name || name === 'user' || name === 'identity') && participant.metadata) {
                try {
                    const meta = JSON.parse(participant.metadata);
                    if (meta.name) name = meta.name;
                    if (meta.displayName) name = meta.displayName;
                } catch {
                    // Metadata was not JSON or didn't contain name
                }
            }

            const finalName = (name === 'user' || name === 'identity' || name.trim() === '')
                ? 'Player'
                : name;

            setDisplayName(finalName);
        };

        updateName();

        participant.on(ParticipantEvent.NameChanged, updateName);
        participant.on(ParticipantEvent.MetadataChanged, updateName);

        return () => {
            participant.off(ParticipantEvent.NameChanged, updateName);
            participant.off(ParticipantEvent.MetadataChanged, updateName);
        };
    }, [participant]);

    return (
        <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="absolute top-4 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 rounded-full
            bg-gradient-to-br from-lime-700/60 via-lime-900/60 to-emerald-900/60
            p-2 pr-5 backdrop-blur-md border border-lime-400/40 shadow-xl ring-1 ring-lime-300/20"
        >
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 text-red-800 shadow-sm">
                <CricketBallIcon className="size-6" />
                <span className="sr-only">Player Icon</span>
            </div>
            <div className="flex flex-col">
                <span className="text-[10px] uppercase font-bold text-yellow-300/80 tracking-wider">Batsman</span>
                <span className="text-sm font-extrabold text-white leading-none tracking-wide">{displayName}</span>
            </div>
        </motion.div>
    );
}

interface SessionViewProps {
    appConfig: AppConfig;
}

export const SessionView = ({
    appConfig,
    ...props
}: React.ComponentProps<'section'> & SessionViewProps) => {
    useConnectionTimeout(200_000);
    useDebugMode({ enabled: IN_DEVELOPMENT });

    const { localParticipant } = useLocalParticipant();

    const messages = useChatMessages();
    const [chatOpen, setChatOpen] = useState(false);
    const scrollAreaRef = useRef<HTMLDivElement>(null);

    const controls: ControlBarControls = {
        leave: true,
        microphone: true,
        chat: appConfig.supportsChatInput,
        camera: appConfig.supportsVideoInput,
        screenShare: appConfig.supportsVideoInput,
    };

    useEffect(() => {
        const lastMessage = messages.at(-1);
        const lastMessageIsLocal = lastMessage?.from?.isLocal === true;

        if (scrollAreaRef.current && lastMessageIsLocal) {
            scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
        }
    }, [messages]);

    return (
        <section
            className="relative z-10 h-full w-full overflow-hidden"
            {...props}
        >
            {/* Background: STADIUM NIGHT VIEW (Option 2) */}
            <div aria-hidden="true" className="absolute inset-0 -z-10 select-none overflow-hidden">
                {/* Dark Base with Radial Gradient (Spotlight effect) */}
                <div className="absolute inset-0 bg-black" />
                <div
                    className="absolute inset-0"
                    style={{
                        backgroundImage: `radial-gradient(circle at center, rgba(132, 204, 22, 0.15) 0%, rgba(0, 0, 0, 0.9) 70%)`,
                        opacity: 1,
                    }}
                />

                {/* Floating 'Stadium Lights' (subtle white circles) */}
                <div className="absolute top-[10%] left-[10%] h-12 w-12 rounded-full bg-white/5 blur-xl" />
                <div className="absolute top-[5%] right-[20%] h-8 w-8 rounded-full bg-white/5 blur-xl" />
                <div className="absolute bottom-[15%] left-[15%] h-10 w-10 rounded-full bg-white/5 blur-xl" />
            </div>

            {/* Player Badge - Centered at the top */}
            <PlayerBadge participant={localParticipant} />

            {/* Chat Transcript -> Maximized for full screen chat view */}
            <div
                className={cn(
                    'fixed inset-0 grid grid-cols-1 grid-rows-1',
                    !chatOpen && 'pointer-events-none'
                )}
            >
                <Fade top className="absolute inset-x-0 top-0 h-40" />

                <ScrollArea
                    ref={scrollAreaRef}
                    className="px-4 pt-40 pb-[150px] md:px-12 md:pb-[180px] w-full"
                >
                    <ChatTranscript
                        hidden={!chatOpen}
                        messages={messages}
                        className="mx-auto max-w-4xl space-y-3 transition-opacity duration-300 ease-out"
                    />
                </ScrollArea>
            </div>

            {/* Tile Layout (Agent Visuals) */}
            <TileLayout chatOpen={chatOpen} />

            {/* Bottom Controls -> Maximized control bar */}
            <MotionBottom
                {...BOTTOM_VIEW_MOTION_PROPS}
                className="fixed inset-x-0 bottom-0 z-50 px-3 md:px-12"
            >
                {appConfig.isPreConnectBufferEnabled && (
                    <PreConnectMessage messages={messages} className="pb-4" />
                )}

                <div className="relative mx-auto max-w-4xl pb-3 md:pb-12">
                    <Fade bottom className="absolute inset-x-0 top-0 h-4 -translate-y-full" />
                    <AgentControlBar controls={controls} onChatOpenChange={setChatOpen} />
                </div>
            </MotionBottom>
        </section>
    );
};
