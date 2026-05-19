"use client";

import React, { useEffect, useState } from "react";

export default function ShootingStarsOverlay() {
  const [stars, setStars] = useState<
    Array<{
      id: number;
      top: number;
      left: number;
      delay: number;
      duration: number;
      scale: number;
      opacity: number;
    }>
  >([]);

  useEffect(() => {
    // Generate 8 randomized stars to keep it subtle and elegant
    const newStars = Array.from({ length: 8 }).map((_, i) => ({
      id: i,
      // Random starting positions predominantly in the top-right quadrant
      top: Math.random() * 50 - 20, // -20% to 30% from top
      left: Math.random() * 50 + 50, // 50% to 100% from left
      // Random delays from 0s to 20s
      delay: Math.random() * 20,
      // Random duration from 4s to 10s to ensure different speeds
      duration: Math.random() * 6 + 4,
      // Random scale to simulate distance (0.5 to 1.5)
      scale: Math.random() * 1 + 0.5,
      // Random peak opacity for fading (0.4 to 1)
      opacity: Math.random() * 0.6 + 0.4,
    }));
    
    setStars(newStars);
  }, []);

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden z-0">
      {stars.map((star) => (
        <div
          key={star.id}
          className="absolute w-[180px] h-[1.5px] bg-gradient-to-r from-transparent via-blue-200/80 to-white rounded-full shadow-[0_0_15px_rgba(191,219,254,0.9)] opacity-0 animate-premium-shooting-star blur-[0.5px]"
          style={{
            top: `${star.top}%`,
            left: `${star.left}%`,
            animationDelay: `${star.delay}s`,
            animationDuration: `${star.duration}s`,
            animationTimingFunction: "cubic-bezier(0.25, 1, 0.5, 1)",
            // Use custom CSS variables to pass randomized values to keyframes
            "--star-scale": star.scale,
            "--star-opacity": star.opacity,
          } as React.CSSProperties}
        />
      ))}
    </div>
  );
}
