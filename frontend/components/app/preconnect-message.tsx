'use client';

import { AnimatePresence, motion } from 'motion/react';
import { type ReceivedChatMessage } from '@livekit/components-react';
import { ShimmerText } from '@/components/livekit/shimmer-text';
import { cn } from '@/lib/utils';

const MotionMessage = motion.create('p');

const VIEW_MOTION_PROPS = {
    variants: {
        visible: {
            opacity: 1,
            transition: {
                ease: 'easeIn',
                duration: 0.5,
                delay: 0.8,
            },
        },
        hidden: {
            opacity: 0,
            transition: {
                ease: 'easeIn',
                duration: 0.5,
                delay: 0,
            },
        },
    },
    initial: 'hidden',
    animate: 'visible',
    exit: 'hidden',
};

interface PreConnectMessageProps {
    messages?: ReceivedChatMessage[];
    className?: string;
}

export function PreConnectMessage({ className, messages = [] }: PreConnectMessageProps) {
    return (
        <AnimatePresence>
            {messages.length === 0 && (
                <MotionMessage
                    {...VIEW_MOTION_PROPS}
                    aria-hidden={messages.length > 0}
                    // UPDATED: Added Scoreboard styling
                    className={cn(
                        'pointer-events-none text-center inline-flex justify-center w-full py-2 px-6 rounded-xl',
                        'bg-black/80 backdrop-blur-sm border border-lime-500/30',
                        'shadow-lg shadow-lime-500/20', // Cricket green glow
                        className
                    )}
                >
                    <ShimmerText className="text-sm font-semibold">
                        Umpire is waiting for the toss... get ready! {/* UPDATED: Cricket-themed message */}
                    </ShimmerText>
                </MotionMessage>
            )}
        </AnimatePresence>
    );
}
