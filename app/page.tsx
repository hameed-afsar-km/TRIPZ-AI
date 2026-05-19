"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { PromptInputBox } from "@/components/ui/ai-prompt-box";
import ShootingStarsOverlay from "@/components/ui/shooting-stars-overlay";
import {
  Compass,
  Sparkles,
  MapPin,
  DollarSign,
  Plane,
  Activity,
  Hotel,
  Train,
  Clock,
  ArrowRight
} from "lucide-react";

interface AgentMessage {
  id: string;
  agent: "Planner" | "Budget" | "Logistics" | "Guide";
  status: "thinking" | "completed";
  text: string;
  timestamp: string;
}

export default function Home() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(-1);
  const [simulationLogs, setSimulationLogs] = useState<AgentMessage[]>([]);
  const [showItinerary, setShowItinerary] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);

  const runAgentSimulation = async (userInput: string) => {
    setHasStarted(true);
    setIsProcessing(true);
    setShowItinerary(false);
    setSimulationLogs([]);
    setActiveStep(0);

    const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    // Step 0: Planner Agent begins
    setSimulationLogs(prev => [
      ...prev,
      {
        id: "1",
        agent: "Planner",
        status: "thinking",
        text: `Analyzing destination options & routing for: "${userInput}"...`,
        timestamp: "10:00:01"
      }
    ]);
    await sleep(2000);

    setSimulationLogs(prev =>
      prev.map(log => log.id === "1" ? { ...log, status: "completed", text: "Established core 5-day route and baseline locations." } : log)
    );

    // Step 1: Budget Agent joins
    setActiveStep(1);
    setSimulationLogs(prev => [
      ...prev,
      {
        id: "2",
        agent: "Budget",
        status: "thinking",
        text: "Scanning flight aggregators and boutique hotels for optimal pricing structure...",
        timestamp: "10:00:03"
      }
    ]);
    await sleep(2000);

    setSimulationLogs(prev =>
      prev.map(log => log.id === "2" ? { ...log, status: "completed", text: "Found stays under budget. Applied 15% partner loyalty discount." } : log)
    );

    // Step 2: Logistics Agent joins
    setActiveStep(2);
    setSimulationLogs(prev => [
      ...prev,
      {
        id: "3",
        agent: "Logistics",
        status: "thinking",
        text: "Synthesizing transit alternatives (train routes, local shuttles, walking distances)...",
        timestamp: "10:00:06"
      }
    ]);
    await sleep(2000);

    setSimulationLogs(prev =>
      prev.map(log => log.id === "3" ? { ...log, status: "completed", text: "Built step-by-step train schedules and local transfer connections." } : log)
    );

    // Step 3: Local Guide Agent joins
    setActiveStep(3);
    setSimulationLogs(prev => [
      ...prev,
      {
        id: "4",
        agent: "Guide",
        status: "thinking",
        text: "Curating hidden culinary gems and off-beat historical attractions...",
        timestamp: "10:00:08"
      }
    ]);
    await sleep(2000);

    setSimulationLogs(prev =>
      prev.map(log => log.id === "4" ? { ...log, status: "completed", text: "Added curated local dining spots and reservation recommendations." } : log)
    );

    // Done
    setActiveStep(4);
    await sleep(800);
    setIsProcessing(false);
    setShowItinerary(true);
  };

  const handleSend = (msg: string) => {
    if (!msg || msg.trim() === "") return;
    runAgentSimulation(msg);
  };

  return (
    <div className="h-screen bg-[url('/bg.jpeg')] bg-cover bg-center bg-no-repeat text-[#f4f4f5] font-sans selection:bg-orange-500/30 selection:text-orange-400 relative overflow-hidden flex flex-col justify-between p-4 md:p-6">

      {/* Dark frosted glass overlay for readability & image colors blending */}
      <div className="absolute inset-0 bg-[#09090b]/85 backdrop-blur-[3px] -z-10"></div>

      {/* Background glow effects matching orange theme */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-orange-600/10 rounded-full blur-[140px] pointer-events-none -z-10 animate-pulse duration-[8000ms]"></div>

      {/* Cinematic Shooting Stars Overlay */}
      <ShootingStarsOverlay />

      {/* Main Container (Reduced to max-w-xl for compact Chat UI width) */}
      <div className="flex-1 max-w-xl w-full mx-auto flex flex-col justify-between relative z-10 h-full">

        {/* Header showing logo only when active */}
        {hasStarted && (
          <div className="text-center py-2 border-b border-zinc-800/40">
            <motion.span
              layoutId="tripz-logo"
              className="inline-block font-kenyan italic font-black text-3xl tracking-widest text-orange-500 drop-shadow-[0_0_15px_rgba(234,88,12,0.5)]"
            >
              TRIPZ
            </motion.span>
          </div>
        )}

        {/* Chat / Visualization Screen */}
        <div className="flex-1 flex flex-col justify-center overflow-y-auto scrollbar-none py-4 space-y-6">
          {!hasStarted ? (
            // Centered Welcome View with Kenyan Coffee TRIPZ font
            <div className="flex flex-col items-center justify-start h-full pt-[16vh] space-y-4">
              <motion.h1
                layoutId="tripz-logo"
                className="font-kenyan italic font-black text-8xl md:text-[8.5rem] lg:text-[10rem] tracking-wider select-none retro-text leading-none"
              >
                TRIPZ
              </motion.h1>
              <p className="text-zinc-300 text-sm max-w-sm text-center leading-relaxed font-sans bg-zinc-950/40 p-4 rounded-2xl border border-zinc-800/30 backdrop-blur-sm shadow-xl">
                Enter your travel coordinates. Our collaborative AI agents will coordinate and draft a consensus itinerary.
              </p>
            </div>
          ) : (
            // Active Stream & Results View
            <div className="space-y-6 max-h-full overflow-y-auto pr-1">

              {/* Agent Orchestrator Visualizer Status */}
              <div className="grid grid-cols-4 gap-2 border-b border-zinc-800/40 pb-4">
                {[
                  { name: "Planner", icon: Compass, step: 0 },
                  { name: "Budget", icon: DollarSign, step: 1 },
                  { name: "Transit", icon: Plane, step: 2 },
                  { name: "Curator", icon: MapPin, step: 3 }
                ].map((agent, i) => {
                  const isActive = activeStep === agent.step;
                  const isCompleted = activeStep > agent.step;
                  return (
                    <div
                      key={i}
                      className={`flex flex-col items-center justify-center p-2 rounded-xl border transition-all duration-300 ${isActive
                        ? "border-orange-500/50 bg-orange-950/10"
                        : isCompleted
                          ? "border-orange-500/20 bg-zinc-900/40 opacity-80"
                          : "border-zinc-800/60 bg-zinc-900/10 opacity-40"
                        }`}
                    >
                      <agent.icon className={`h-4 w-4 ${isActive || isCompleted ? "text-orange-500" : "text-zinc-500"}`} />
                      <span className="text-[9px] font-bold mt-1 text-zinc-400">{agent.name}</span>
                    </div>
                  );
                })}
              </div>

              {/* Agent Consensus Stream */}
              <div className="border border-zinc-800/80 rounded-2xl bg-zinc-950/80 p-5 shadow-xl relative space-y-4">
                <div className="absolute top-3 right-4 flex items-center gap-1.5">
                  <span className="text-[9px] font-mono text-zinc-500">AGENT FLOW</span>
                  <span className="h-1.5 w-1.5 rounded-full bg-orange-500 animate-pulse"></span>
                </div>

                <h3 className="font-bold text-[10px] tracking-wider text-orange-400 uppercase flex items-center gap-1.5">
                  <Activity className="h-3.5 w-3.5 text-orange-500" />
                  Consensus Stream
                </h3>

                <div className="space-y-3.5 font-mono text-[11px] text-zinc-300">
                  {simulationLogs.map((log) => (
                    <div key={log.id} className="border-l border-orange-500/20 pl-3 py-0.5">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold uppercase ${log.agent === "Planner" ? "bg-blue-500/10 text-blue-400" :
                          log.agent === "Budget" ? "bg-emerald-500/10 text-emerald-400" :
                            log.agent === "Logistics" ? "bg-amber-500/10 text-amber-400" :
                              "bg-purple-500/10 text-purple-400"
                          }`}>
                          {log.agent}
                        </span>
                        {log.status === "thinking" ? (
                          <span className="text-zinc-500 animate-pulse italic">Negotiating...</span>
                        ) : (
                          <span className="text-orange-500 font-bold">Approved</span>
                        )}
                      </div>
                      <p className="text-zinc-400 leading-relaxed">{log.text}</p>
                    </div>
                  ))}

                  {isProcessing && activeStep >= 0 && activeStep < 4 && (
                    <div className="flex items-center gap-2 text-zinc-500 italic pl-3 border-l border-dashed border-zinc-800">
                      <Clock className="h-3 w-3 animate-spin" />
                      <span>Negotiating consensus parameters...</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Itinerary Results Grid */}
              {showItinerary && (
                <div className="bg-zinc-900/35 border border-zinc-800/80 rounded-2xl p-5 animate-in fade-in-50 duration-500 shadow-xl space-y-4">
                  <div className="flex justify-between items-center border-b border-zinc-800/60 pb-3">
                    <div>
                      <h3 className="text-lg font-black text-white">Consensus Itinerary</h3>
                      <p className="text-zinc-400 text-[11px] mt-0.5">5 Days • 2 Adults • Total Cost: $1,420</p>
                    </div>
                    <button className="bg-white hover:bg-zinc-200 text-black font-extrabold text-[10px] px-3 py-1.5 rounded-lg transition-all flex items-center gap-1">
                      Book Plan
                      <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>

                  <div className="space-y-4">
                    {[
                      {
                        day: "D1",
                        title: "Kyoto Arrival & Tea Houses",
                        stay: "Hotel Resol Trinity Kyoto (4.5★)",
                        transit: "Haruka Express from KIX"
                      },
                      {
                        day: "D2",
                        title: "Bamboo Groves & Scenic Mountain Stays",
                        stay: "Hotel Resol Trinity Kyoto (4.5★)",
                        transit: "Hankyu Kyoto Line Shuttle"
                      },
                      {
                        day: "D3",
                        title: "Tokyo Bullet Transfer & Shinjuku Neon",
                        stay: "The Knot Tokyo Shinjuku (4.4★)",
                        transit: "Nozomi Shinkansen"
                      }
                    ].map((dayPlan, index) => (
                      <div key={index} className="flex gap-3">
                        <div className="w-8 h-8 rounded-lg bg-orange-950/30 border border-orange-500/30 flex items-center justify-center text-[11px] font-bold text-orange-400 flex-shrink-0">
                          {dayPlan.day}
                        </div>
                        <div className="flex-1 bg-zinc-950/40 border border-zinc-800/40 rounded-xl p-3">
                          <h4 className="font-extrabold text-xs text-zinc-100">{dayPlan.title}</h4>
                          <div className="flex gap-4 mt-2 text-[10px]">
                            <span className="text-zinc-400 flex items-center gap-1">
                              <Hotel className="h-3 w-3 text-orange-500/80" />
                              {dayPlan.stay}
                            </span>
                            <span className="text-zinc-400 flex items-center gap-1">
                              <Train className="h-3 w-3 text-orange-500/80" />
                              {dayPlan.transit}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            </div>
          )}
        </div>

        {/* Input box fixed at bottom */}
        <div className="w-full pb-16 pt-4 bg-transparent">
          <PromptInputBox
            onSend={handleSend}
            isLoading={isProcessing}
            placeholder="Plan a route or state coordinates..."
          />
          <div className="text-[10px] text-white-500 text-center mt-2 flex items-center justify-center gap-1">
            <Sparkles className="h-3 w-3 text-orange-500/70" />
            <span>Multi-Agent debate triggers automatically upon input.</span>
          </div>
        </div>

      </div>
    </div>
  );
}
