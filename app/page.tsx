"use client";

import React, { useState, useRef } from "react";
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform } from "framer-motion";
import { PromptInputBox } from "@/components/ui/ai-prompt-box";
import ShootingStarsOverlay from "@/components/ui/shooting-stars-overlay";
import {
  Compass,
  Sparkles,
  MapPin,
  DollarSign,
  Plane,
  BrainCircuit,
  CheckCircle2,
  Loader2,
  MessageSquare,
  Bot,
  X
} from "lucide-react";

interface AgentMessage {
  id: string;
  agent: "Planner" | "Budget" | "Transit" | "Curator";
  status: "thinking" | "completed";
  text: string;
  timestamp: string;
}

const isTripRelated = (text: string): boolean => {
  let cleanText = text;
  if (text.startsWith("[History Context:") && text.endsWith("]")) {
    cleanText = text.slice(17, -1);
  }
  
  const normalized = cleanText.toLowerCase().trim();
  
  if (normalized.length < 3) {
    return false;
  }
  
  const travelKeywords = [
    "trip", "travel", "plan", "itinerary", "visit", "vacation", "holiday", 
    "tour", "flight", "hotel", "budget", "route", "explore", "stay", 
    "day", "week", "night", "destination", "country", "city", "transport",
    "cost", "pricing", "attraction", "sightseeing", "museum", "park", "beach",
    "map", "coordinate", "activities", "schedule", "guide"
  ];
  
  const geographicKeywords = [
    "tokyo", "paris", "london", "rome", "kyoto", "osaka", "bali", "new york", "hawaii", "sydney", "barcelona",
    "japan", "france", "italy", "spain", "usa", "uk", "india", "germany", "canada", "australia", "china",
    "mexico", "brazil", "egypt", "greece", "thailand", "vietnam", "singapore", "malaysia", "switzerland"
  ];

  const hasTravelKeyword = travelKeywords.some(keyword => normalized.includes(keyword));
  if (hasTravelKeyword) return true;

  const hasGeographicKeyword = geographicKeywords.some(geo => normalized.includes(geo));
  if (hasGeographicKeyword) return true;

  const travelPatterns = /\b(to|in|at|visit|explore|around|go)\s+[a-z]+/i;
  if (travelPatterns.test(normalized)) return true;

  return false;
};

export default function Home() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(-1);
  const [simulationLogs, setSimulationLogs] = useState<AgentMessage[]>([]);
  const [simulationStage, setSimulationStage] = useState<"idle" | "parsing" | "agents" | "done">("idle");
  const [itineraryResult, setItineraryResult] = useState<any>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // 3D Parallax Mouse Tracking
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const springConfig = { damping: 25, stiffness: 150 };
  const springX = useSpring(mouseX, springConfig);
  const springY = useSpring(mouseY, springConfig);

  const bgX = useTransform(springX, [-0.5, 0.5], ["-3%", "3%"]);
  const bgY = useTransform(springY, [-0.5, 0.5], ["-3%", "3%"]);

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    mouseX.set(x);
    mouseY.set(y);
  };

  const runAgentSimulation = async (userInput: string) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setSimulationStage("parsing");
    setIsProcessing(true);
    setSimulationLogs([]);
    setActiveStep(-1);
    setItineraryResult(null);

    try {
      const response = await fetch("http://localhost:8000/api/v1/plan/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_request: userInput, stream: true }),
        signal: controller.signal,
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        let done = false;
        let buffer = "";
        let logCounter = 1;

        while (!done) {
          const { value, done: readerDone } = await reader.read();
          done = readerDone;
          if (value) {
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop() || "";
            
            for (const chunk of lines) {
              const eventMatch = chunk.match(/event:\s*(.*)/);
              const dataMatch = chunk.match(/data:\s*(.*)/);
              
              if (eventMatch && dataMatch) {
                const eventType = eventMatch[1].trim();
                const dataStr = dataMatch[1].trim();
                const data = JSON.parse(dataStr);

                if (eventType === "agent_start") {
                  setSimulationStage("agents");
                  
                  let mappedAgent = "Planner";
                  let step = 0;
                  if (data.agent === "budget_agent" || data.agent === "parallel_tools") { mappedAgent = "Budget"; step = 1; }
                  else if (data.agent === "itinerary_agent") { mappedAgent = "Transit"; step = 2; }
                  else if (data.agent === "critic_agent" || data.agent === "replanning_agent") { mappedAgent = "Curator"; step = 3; }
                  
                  setActiveStep(step);
                  setSimulationLogs(prev => [...prev, {
                    id: String(logCounter++),
                    agent: mappedAgent as any,
                    status: "thinking",
                    text: data.message || `Running ${data.agent}...`,
                    timestamp: new Date().toLocaleTimeString()
                  }]);
                } else if (eventType === "agent_complete") {
                  setSimulationLogs(prev => {
                    const newLogs = [...prev];
                    if (newLogs.length > 0) {
                      newLogs[newLogs.length - 1].status = "completed";
                      if (data.preview && Object.keys(data.preview).length > 0) {
                        const previewText = JSON.stringify(data.preview)
                           .replace(/["{}]/g, "")
                           .replace(/:/g, ": ")
                           .replace(/,/g, " | ");
                        newLogs[newLogs.length - 1].text += ` → ${previewText}`;
                      }
                    }
                    return newLogs;
                  });
                } else if (eventType === "done") {
                  setItineraryResult(data);
                  setActiveStep(4);
                  setSimulationStage("done");
                  setIsProcessing(false);
                } else if (eventType === "error") {
                  setSimulationLogs(prev => [...prev, {
                    id: String(logCounter++),
                    agent: "Planner",
                    status: "completed",
                    text: `Error: ${data.message}`,
                    timestamp: new Date().toLocaleTimeString()
                  }]);
                  setIsProcessing(false);
                  setSimulationStage("done");
                }
              }
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name === "AbortError") {
        console.log("Fetch aborted by user");
        return;
      }
      console.error(error);
      setSimulationLogs(prev => [...prev, {
        id: "error",
        agent: "Planner",
        status: "completed",
        text: `Network Error: Could not connect to backend.`,
        timestamp: new Date().toLocaleTimeString()
      }]);
      setIsProcessing(false);
      setSimulationStage("done");
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
    }
  };

  const handleSend = (msg: string) => {
    if (!msg || msg.trim() === "") return;
    
    if (!isTripRelated(msg)) {
      setValidationError("Please type a request related to trip planning (e.g., '3 days in Tokyo', 'Paris budget route', or 'explore Rome').");
      return;
    }
    
    setValidationError(null);
    runAgentSimulation(msg);
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsProcessing(false);
    setSimulationStage("done");
    setValidationError("Generation stopped by the user.");
  };

  const bentoAgents = [
    { name: "Planner", icon: Compass, step: 0 },
    { name: "Transit", icon: Plane, step: 2 },
    { name: "Budget", icon: DollarSign, step: 1 },
    { name: "Curator", icon: MapPin, step: 3 }
  ];

  return (
    <div 
      onMouseMove={handleMouseMove}
      className="h-screen text-[#f4f4f5] font-sans selection:bg-orange-500/30 selection:text-orange-400 relative overflow-hidden flex flex-col justify-between"
    >
      {/* Background Image with 3D Parallax */}
      <motion.div
        className="absolute inset-[-5%] bg-[url('/bg.jpeg')] bg-cover bg-center bg-no-repeat -z-20"
        style={{ x: bgX, y: bgY }}
      />

      {/* Dark frosted glass overlay for readability & image colors blending */}
      <div className="absolute inset-0 bg-[#09090b]/85 backdrop-blur-[3px] -z-10 pointer-events-none"></div>

      {/* Background glow effects matching orange theme */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-orange-600/10 rounded-full blur-[140px] pointer-events-none -z-10 animate-pulse duration-[8000ms]"></div>

      {/* Cinematic Shooting Stars Overlay */}
      <ShootingStarsOverlay />

      {/* Header showing logo dynamically */}
      <div className="absolute top-0 left-0 right-0 z-50 flex justify-center py-4 pointer-events-none">
        <AnimatePresence>
          {simulationStage !== "idle" && (
            <motion.div
              layoutId="tripz-logo-container"
              initial={{ opacity: 0, y: -20, scale: 0.8 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ type: "spring", stiffness: 200, damping: 20 }}
            >
              <span className="inline-block font-kenyan italic font-black text-4xl tracking-widest text-orange-500 drop-shadow-[0_0_15px_rgba(234,88,12,0.8)] pointer-events-auto">
                TRIPZ
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Main Container */}
      <div className="flex-1 max-w-4xl w-full mx-auto flex flex-col justify-between relative z-10 h-full p-4 md:p-6 pt-20">

        {/* Chat / Visualization Screen */}
        <div className="flex-1 flex flex-col justify-center overflow-y-auto scrollbar-none py-4">
          <AnimatePresence mode="wait">
            {simulationStage === "idle" && (
              <motion.div
                key="idle"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9, filter: "blur(10px)" }}
                transition={{ duration: 0.4 }}
                className="flex flex-col items-center justify-center h-full pt-[8vh] space-y-6"
              >
                <motion.div layoutId="tripz-logo-container">
                  <h1 className="font-kenyan italic font-black text-8xl md:text-[8.5rem] lg:text-[10rem] tracking-wider select-none retro-text leading-none">
                    TRIPZ
                  </h1>
                </motion.div>
                <p className="text-zinc-300 text-sm max-w-sm text-center leading-relaxed font-sans bg-zinc-950/40 p-4 rounded-2xl border border-zinc-800/30 backdrop-blur-sm shadow-xl">
                  Enter your travel coordinates. Our collaborative AI agents will coordinate and draft a consensus itinerary.
                </p>
              </motion.div>
            )}

            {simulationStage === "parsing" && (
              <motion.div
                key="parsing"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.9, filter: "blur(10px)" }}
                transition={{ duration: 0.5 }}
                className="flex flex-col items-center justify-center h-full"
              >
                <div className="relative flex flex-col items-center p-10 bg-white/5 border border-white/10 rounded-[2rem] shadow-[0_8px_32px_0_rgba(0,0,0,0.3)] backdrop-blur-xl max-w-md w-full text-center">
                  <div className="absolute inset-0 bg-gradient-to-b from-orange-500/10 to-transparent rounded-[2rem] opacity-50"></div>
                  <BrainCircuit className="w-16 h-16 text-orange-500 animate-pulse mb-6 drop-shadow-[0_0_15px_rgba(234,88,12,0.8)]" />
                  <h2 className="text-2xl font-bold text-white mb-2">Orchestrator Parsing Request</h2>
                  <p className="text-zinc-400 text-sm">Analyzing input and preparing agent workspaces...</p>
                  <div className="mt-8 w-full bg-zinc-800/50 rounded-full h-1.5 overflow-hidden">
                    <motion.div 
                      className="h-full bg-orange-500"
                      initial={{ width: "0%" }}
                      animate={{ width: "100%" }}
                      transition={{ duration: 2, ease: "easeInOut", repeat: Infinity }}
                    />
                  </div>
                </div>
              </motion.div>
            )}

            {(simulationStage === "agents" || simulationStage === "done") && (
              <motion.div
                key="agents"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, staggerChildren: 0.1 }}
                className="flex flex-col h-full space-y-6 overflow-y-auto pr-2 pb-10"
              >
                {/* 4 Bento Grids */}
                <div className="grid grid-cols-2 gap-4 flex-shrink-0">
                  {bentoAgents.map((agent, i) => {
                    const isActive = activeStep === agent.step;
                    const isCompleted = activeStep > agent.step;
                    const isPending = activeStep < agent.step;
                    const logs = simulationLogs.filter(l => l.agent === agent.name);
                    
                    return (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: i * 0.1 }}
                        className={`relative overflow-hidden flex flex-col p-5 rounded-3xl border transition-all duration-500 ${
                          isActive
                            ? "border-orange-500/50 bg-orange-950/20 shadow-[0_0_30px_rgba(234,88,12,0.15)]"
                            : isCompleted
                              ? "border-zinc-700/60 bg-zinc-900/40"
                              : "border-zinc-800/40 bg-zinc-950/40 opacity-60"
                        } backdrop-blur-md h-36`}
                      >
                        <div className="flex items-center justify-between mb-3 shrink-0">
                          <div className="flex items-center gap-2">
                            <div className={`p-2 rounded-xl transition-colors duration-500 ${isActive ? 'bg-orange-500/20 text-orange-400' : isCompleted ? 'bg-zinc-800 text-zinc-300' : 'bg-zinc-900 text-zinc-600'}`}>
                              <agent.icon className="h-4 w-4" />
                            </div>
                            <span className={`font-bold tracking-wide text-sm transition-colors duration-500 ${isActive || isCompleted ? 'text-white' : 'text-zinc-500'}`}>{agent.name}</span>
                          </div>
                          {isActive && <Loader2 className="h-4 w-4 text-orange-500 animate-spin" />}
                          {isCompleted && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
                        </div>
                        
                        <div className="flex-1 text-xs text-zinc-400 font-mono overflow-y-auto scrollbar-none flex flex-col justify-end">
                          {isPending && <span className="text-zinc-600 italic">Waiting...</span>}
                          {logs.map((log, idx) => (
                            <div key={idx} className="mb-1 last:mb-0 line-clamp-2">
                              <span className="text-zinc-500 mr-2">[{log.timestamp}]</span>
                              <span className={log.status === 'completed' ? 'text-emerald-400/80' : 'text-orange-300/80'}>{log.text}</span>
                            </div>
                          ))}
                        </div>

                        {isActive && (
                          <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-orange-500 to-transparent animate-pulse" />
                        )}
                      </motion.div>
                    );
                  })}
                </div>

                {/* Final ChatGPT-style Output */}
                <AnimatePresence>
                  {simulationStage === "done" && itineraryResult && (
                    <motion.div
                      initial={{ opacity: 0, y: 30, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ duration: 0.6, type: "spring", bounce: 0.4 }}
                      className="flex gap-4 mt-6"
                    >
                      <div className="w-8 h-8 rounded-full bg-orange-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-orange-600/20 mt-1">
                        <Bot className="w-4 h-4 text-white" />
                      </div>
                      <div className="flex-1 bg-zinc-900/60 p-6 rounded-3xl border border-zinc-800/60 backdrop-blur-md">
                        {itineraryResult.itinerary?.markdown ? (
                          <div className="text-sm leading-relaxed text-zinc-300 space-y-4">
                            {itineraryResult.itinerary.markdown.split('\n').map((line: string, i: number) => (
                              <p key={i}>{line}</p>
                            ))}
                          </div>
                        ) : (
                          <div className="text-sm leading-relaxed">
                            <h3 className="text-xl font-bold text-white mb-2">{itineraryResult.itinerary?.title || "Consensus Itinerary"}</h3>
                            <p className="text-zinc-400 mb-6">Total Cost: ${itineraryResult.itinerary?.total_estimated_cost || 0}</p>
                            
                            <div className="space-y-6">
                              {(itineraryResult.itinerary?.days || []).map((day: any, i: number) => (
                                <div key={i} className="border-l-2 border-orange-500/30 pl-4">
                                  <h4 className="font-bold text-white">Day {day.day}: {day.theme}</h4>
                                  <ul className="mt-2 space-y-1 text-zinc-300">
                                    {day.morning && <li><span className="text-orange-400 font-medium">Morning:</span> {day.morning}</li>}
                                    {day.afternoon && <li><span className="text-orange-400 font-medium">Afternoon:</span> {day.afternoon}</li>}
                                    {day.evening && <li><span className="text-orange-400 font-medium">Evening:</span> {day.evening}</li>}
                                  </ul>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Input box fixed at bottom */}
        <div className="w-full pb-8 pt-4 bg-transparent mt-auto flex-shrink-0 relative">
          <AnimatePresence>
            {validationError && (
              <motion.div
                initial={{ opacity: 0, y: 15, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 15, scale: 0.95 }}
                className="absolute bottom-full left-0 right-0 mb-3 mx-auto max-w-lg bg-[#09090b]/85 border border-orange-500/30 backdrop-blur-md p-4 rounded-2xl flex items-center justify-between shadow-2xl text-xs text-zinc-200 z-50"
              >
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-orange-500/10 text-orange-400">
                    <Sparkles className="h-4 w-4 animate-pulse" />
                  </div>
                  <span className="leading-relaxed">{validationError}</span>
                </div>
                <button 
                  onClick={() => setValidationError(null)}
                  className="text-zinc-400 hover:text-white p-1 hover:bg-zinc-800/50 rounded-lg transition-all ml-2"
                >
                  <X className="h-4 w-4" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          <PromptInputBox
            onSend={handleSend}
            onStop={handleStop}
            isLoading={isProcessing}
            placeholder="Plan a route or state coordinates..."
          />
          <div className="text-[10px] text-white-500 text-center mt-3 flex items-center justify-center gap-1 opacity-70">
            <Sparkles className="h-3 w-3 text-orange-500" />
            <span>Multi-Agent debate triggers automatically upon input.</span>
          </div>
        </div>

      </div>
    </div>
  );
}
