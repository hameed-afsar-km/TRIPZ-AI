"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform } from "framer-motion";
import { PromptInputBox } from "@/components/ui/ai-prompt-box";
import { HistorySidebar } from "@/components/ui/history-sidebar";
import ShootingStarsOverlay from "@/components/ui/shooting-stars-overlay";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import LoginButton from "@/components/ui/login-button";
import { useAuth } from "@/lib/auth-context";
import {
  listSessions as fsListSessions,
  loadSession as fsLoadSession,
  deleteSession as fsDeleteSession,
  updateSessionItinerary as fsUpdateItinerary,
  type ChatSession,
} from "@/lib/firestore-service";
import {
  Compass,
  Sparkles,
  MapPin,
  DollarSign,
  Plane,
  BrainCircuit,
  CheckCircle2,
  Loader2,
  Bot,
  X,
  Sun,
  Moon,
  Sunrise,
  Clock,
  Navigation,
  Copy,
  Check,
} from "lucide-react";

interface AgentMessage {
  id: string;
  agent: "Planner" | "Budget" | "Transit" | "Curator" | "Synthesis";
  agentKey: string;
  status: "thinking" | "completed";
  text: string;
  timestamp: string;
  isError?: boolean;
  output?: any;
}

const AGENT_MAP: Record<string, { name: "Planner" | "Budget" | "Transit" | "Curator" | "Synthesis"; step: number }> = {
  "supervisor_agent": { name: "Planner", step: 0 },
  "routing_agent":    { name: "Planner", step: 0 },
  "budget_agent":     { name: "Budget", step: 1 },
  "transit_agent":    { name: "Transit", step: 2 },
  "curator_agent":    { name: "Curator", step: 3 },
  "validator_agent":  { name: "Curator", step: 3 },
  "itinerary_agent":  { name: "Synthesis", step: 4 },
  "critic_agent":     { name: "Synthesis", step: 4 },
  "clarify_node":     { name: "Curator", step: 3 },
};

const ERROR_LABELS: Record<string, { title: string; icon: string }> = {
  quota_exceeded: { title: "API Rate Limit Reached", icon: "⚠️" },
  token_limit_exceeded: { title: "Token Limit Exceeded", icon: "📏" },
};

const formatErrorForDisplay = (type: string, message?: string): string => {
  const label = ERROR_LABELS[type];
  if (label) {
    return `${label.icon} ${label.title}${message ? `: ${message}` : ""}. Try again later or switch providers in Settings.`;
  }
  return message || "An unexpected error occurred.";
};

const AGENT_STATUS_MESSAGES: Record<string, string[]> = {
  supervisor_agent: [
    "Parsing your travel request...",
    "Understanding your preferences...",
    "Extracting destinations & dates...",
    "Analyzing trip requirements...",
    "Identifying key travel details...",
  ],
  routing_agent: [
    "Determining your travel style...",
    "Classifying trip type...",
    "Optimizing for your preferences...",
  ],
  transit_agent: [
    "Checking weather conditions in your destination...",
    "Finding the best transport options...",
    "Making sure the travel is suitable...",
    "Calculating travel distances & times...",
    "Recommending the best route for you...",
  ],
  budget_agent: [
    "Scouting hotel prices in the area...",
    "Estimating daily food & activity costs...",
    "Planning your budget allocation...",
    "Finding the best value accommodations...",
    "Making sure your budget works for the trip...",
  ],
  curator_agent: [
    "Curating the best viewpoints...",
    "Discovering hidden gems in the area...",
    "Finding top attractions & landmarks...",
    "Selecting must-visit spots for you...",
    "Orchestrating the perfect sightseeing plan...",
  ],
  validator_agent: [
    "Filtering non-tourist attractions from your list...",
    "Validating activity quality & relevance...",
    "Checking for tourist-friendly venues...",
    "Removing low-quality suggestions...",
    "Ensuring only the best activities remain...",
  ],
  itinerary_agent: [
    "Crafting your perfect day-by-day plan...",
    "Optimizing your schedule for maximum fun...",
    "Balancing activities, meals & relaxation...",
    "Making sure everything fits your budget...",
    "Arranging the best sequence of activities...",
    "Checking distances between attractions...",
  ],
  critic_agent: [
    "Reviewing itinerary quality & completeness...",
    "Checking budget compliance & accuracy...",
    "Validating the day-by-day flow...",
    "Making sure nothing was missed...",
    "Final quality check on your trip plan...",
  ],
};

function useCyclingMessages(agentKey: string | undefined, intervalMs = 3000): string {
  const messages = agentKey ? AGENT_STATUS_MESSAGES[agentKey] : undefined;
  const [index, setIndex] = React.useState(0);
  React.useEffect(() => {
    if (!messages || messages.length <= 1) return;
    const timer = setInterval(() => setIndex((i) => (i + 1) % messages.length), intervalMs);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentKey, intervalMs]);
  if (!messages || messages.length === 0) return "Working on it...";
  return messages[index % messages.length];
}

function TypingMessageInner({ message, className }: { message: string; className?: string }) {
  const [displayed, setDisplayed] = React.useState("");
  const [showCursor, setShowCursor] = React.useState(true);
  const indexRef = React.useRef(0);

  React.useEffect(() => {
    indexRef.current = 0;
    setDisplayed("");
  }, [message]);

  React.useEffect(() => {
    if (indexRef.current < message.length) {
      const timer = setTimeout(() => {
        setDisplayed(message.slice(0, indexRef.current + 1));
        indexRef.current += 1;
      }, 25);
      return () => clearTimeout(timer);
    }
  }, [displayed, message]);

  React.useEffect(() => {
    const cursor = setInterval(() => setShowCursor((c) => !c), 530);
    return () => clearInterval(cursor);
  }, []);

  return (
    <span className={className}>
      {displayed}
      <span className={`text-orange-400/70 ${showCursor ? "opacity-100" : "opacity-0"}`}>|</span>
    </span>
  );
}

function TypingMessage({ agentKey, className }: { agentKey: string; className?: string }) {
  const message = useCyclingMessages(agentKey, 4000);
  return <TypingMessageInner key={message} message={message} className={className} />;
}

function AgentOutputCard({ log }: { log: AgentMessage }) {
  const [expanded, setExpanded] = React.useState(false);
  const hasOutput = log.output && Object.keys(log.output).length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col gap-1"
    >
      <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
        <CheckCircle2 className="h-3.5 w-3.5" />
        Done
      </span>
      {log.text && (
        <span className="text-zinc-500 text-[10px] md:text-[11px] leading-normal mt-0.5">
          {log.text}
        </span>
      )}
      {hasOutput && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] text-orange-400/70 hover:text-orange-300 mt-1 text-left underline underline-offset-2 decoration-orange-400/30"
        >
          {expanded ? "Hide output" : "View output"}
        </button>
      )}
      {hasOutput && expanded && (
        <motion.pre
          initial={{ opacity: 0, maxHeight: 0 }}
          animate={{ opacity: 1, maxHeight: 400 }}
          exit={{ opacity: 0, maxHeight: 0 }}
          className="text-[10px] text-zinc-400 bg-zinc-900/80 rounded-lg p-2 mt-1 overflow-auto border border-zinc-800 leading-relaxed whitespace-pre-wrap"
        >
          {JSON.stringify(log.output, null, 2)}
        </motion.pre>
      )}
    </motion.div>
  );
}

const isTripRelated = (text: string): boolean => {
  const normalized = text.toLowerCase().trim();
  if (normalized.length < 3) return false;
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

const CURRENCY_SYMBOLS: Record<string, string> = {
  INR: "₹", USD: "$", EUR: "€", GBP: "£", JPY: "¥",
  AUD: "A$", CAD: "C$", AED: "د.إ", SAR: "﷼", SGD: "S$",
  MYR: "RM", THB: "฿", LKR: "Rs", PKR: "₨", EGP: "E£",
  TRY: "₺", CHF: "Fr", SEK: "kr", NOK: "kr", DKK: "kr",
  PLN: "zł", CNY: "¥", HKD: "HK$", KRW: "₩", MXN: "Mex$",
  NZD: "NZ$", ZAR: "R", BRL: "R$",
};

function formatCurrency(amount: number | undefined | null, currencyCode?: string): string {
  if (amount == null || amount === 0) return "—";
  const code = currencyCode || "USD";
  const symbol = CURRENCY_SYMBOLS[code] || code + " ";
  if (amount >= 1e5) return `${symbol}${(amount / 1e5).toFixed(1)}L`;
  if (amount >= 1e3) return `${symbol}${(amount / 1e3).toFixed(1)}K`;
  return `${symbol}${amount.toLocaleString("en-IN")}`;
}

interface DayData {
  day: number;
  theme: string;
  morning?: string;
  afternoon?: string;
  evening?: string;
  estimated_cost?: number;
  budget_tip?: string;
}

interface ItineraryData {
  title?: string;
  total_estimated_cost?: number;
  currency?: string;
  days?: DayData[];
  tips?: string[];
}

interface ItineraryBoardProps {
  itinerary: ItineraryData | null;
  warnings?: string[];
  duration_ms?: number;
}

function ItineraryBoard({ itinerary, warnings, duration_ms }: ItineraryBoardProps) {
  const days = itinerary?.days || [];
  const dayCount = days.length;

  if (dayCount === 0) return null;

  return (
    <div className="flex gap-4 w-full max-w-5xl mx-auto">
      <div className="w-8 h-8 rounded-full bg-orange-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-orange-600/20 mt-1">
        <Bot className="w-4 h-4 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        {/* Summary bar */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between gap-3 mb-5 px-1"
        >
          <div className="min-w-0">
            <h3 className="text-base font-bold text-white truncate">{itinerary?.title || "Consensus Itinerary"}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <Navigation className="h-3 w-3 text-orange-500" />
              <span className="text-zinc-500 text-xs">{dayCount} day{dayCount > 1 ? 's' : ''}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <div className="px-3 py-1 bg-orange-500/10 border border-orange-500/20 rounded-full flex items-center gap-1.5">
              <span className="text-orange-400 font-bold text-sm">{formatCurrency(itinerary?.total_estimated_cost, itinerary?.currency)}</span>
            </div>
            {duration_ms != null && (
              <div className="px-2.5 py-1 bg-zinc-800/60 border border-zinc-700/40 rounded-full flex items-center gap-1">
                <Clock className="h-3 w-3 text-zinc-400" />
                <span className="text-zinc-400 text-[10px]">{(duration_ms / 1000).toFixed(1)}s</span>
              </div>
            )}
          </div>
        </motion.div>

        {/* Timeline */}
        <div className="relative">
          {/* Vertical gradient line */}
          <div className="absolute left-[17px] top-2 bottom-2 w-0.5 bg-gradient-to-b from-orange-500/60 via-purple-500/40 to-transparent" />

          <div className="space-y-5">
            {days.map((day: DayData, i: number) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1, duration: 0.4, ease: "easeOut" }}
                className="relative flex items-start gap-4"
              >
                {/* Timeline node */}
                <div className="shrink-0 relative z-10 flex flex-col items-center pt-1">
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center border transition-all duration-300 ${
                    i === 0
                      ? 'bg-orange-500/20 border-orange-400/50 shadow-[0_0_12px_rgba(234,88,12,0.25)]'
                      : i === dayCount - 1
                        ? 'bg-purple-500/20 border-purple-400/50 shadow-[0_0_12px_rgba(168,85,247,0.25)]'
                        : 'bg-zinc-800/60 border-zinc-700/50'
                  }`}>
                    <span className={`font-bold text-sm ${
                      i === 0 ? 'text-orange-400' : i === dayCount - 1 ? 'text-purple-400' : 'text-zinc-300'
                    }`}>{day.day}</span>
                  </div>
                </div>

                {/* Day card */}
                <div className="flex-1 min-w-0 bg-zinc-900/50 border border-zinc-800/40 rounded-2xl p-4 backdrop-blur-sm min-h-[5rem]">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <h4 className="text-white font-semibold text-sm">{day.theme}</h4>
                    <span className="text-[10px] text-zinc-600 shrink-0 font-mono">DAY {day.day}</span>
                  </div>
                  <div className="space-y-2.5">
                    {day.morning && (
                      <div className="flex items-start gap-3">
                        <div className="shrink-0 w-5 h-5 rounded-md bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mt-0.5">
                          <Sunrise className="h-3 w-3 text-amber-400" />
                        </div>
                        <span className="text-zinc-300 text-[13px] leading-relaxed">{day.morning}</span>
                      </div>
                    )}
                    {day.afternoon && (
                      <div className="flex items-start gap-3">
                        <div className="shrink-0 w-5 h-5 rounded-md bg-orange-500/10 border border-orange-500/20 flex items-center justify-center mt-0.5">
                          <Sun className="h-3 w-3 text-orange-400" />
                        </div>
                        <span className="text-zinc-300 text-[13px] leading-relaxed">{day.afternoon}</span>
                      </div>
                    )}
                    {day.evening && (
                      <div className="flex items-start gap-3">
                        <div className="shrink-0 w-5 h-5 rounded-md bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mt-0.5">
                          <Moon className="h-3 w-3 text-indigo-400" />
                        </div>
                        <span className="text-zinc-300 text-[13px] leading-relaxed">{day.evening}</span>
                      </div>
                    )}
                  </div>
                  {day.estimated_cost != null && (
                    <div className="mt-3 pt-2 border-t border-zinc-800/40 flex items-center justify-between">
                      <span className="text-[11px] text-zinc-500">Day cost</span>
                      <span className="text-[11px] text-orange-400/80 font-mono">{formatCurrency(day.estimated_cost, itinerary?.currency)}</span>
                    </div>
                  )}
                  {day.budget_tip && (
                    <div className="mt-1.5 flex items-start gap-1.5">
                      <span className="text-[10px] text-emerald-500/70 shrink-0 mt-0.5">Tip:</span>
                      <span className="text-[10px] text-zinc-500 leading-relaxed">{day.budget_tip}</span>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Tips */}
        {itinerary?.tips && itinerary.tips.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="mt-5 px-1"
          >
            <div className="text-[11px] text-zinc-500 font-medium mb-2">Tips</div>
            <div className="flex flex-wrap gap-1.5">
              {itinerary.tips.map((tip, i) => (
                <span key={i} className="text-[11px] text-zinc-400 bg-zinc-800/40 px-2.5 py-1 rounded-full">{tip}</span>
              ))}
            </div>
          </motion.div>
        )}

        {/* Footer */}
        {warnings && warnings.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="mt-4 flex items-center gap-2 px-1"
          >
            <MapPin className="h-3 w-3 text-zinc-500 shrink-0" />
            <span className="text-[10px] text-zinc-500">{warnings.join(" | ")}</span>
          </motion.div>
        )}
      </div>
    </div>
  );
}

function BudgetIndicator({ data }: { data: any }) {
  const budget = data.budget || 0;
  const currency = data.currency || "USD";
  const totalCost = budget; // fallback

  const [extractedCost, setExtractedCost] = useState<number | null>(null);
  const [budgetPct, setBudgetPct] = useState(0);

  useEffect(() => {
    if (!data.itinerary?.markdown) return;
    const md = data.itinerary.markdown;
    // Try to extract Grand Total from markdown
    const gtMatch = md.match(/\*\*Grand Total\*\*:\s*~\w+\s*([\d,]+(?:\.\d{1,2})?)/i);
    if (gtMatch) {
      const val = parseFloat(gtMatch[1].replace(/,/g, ""));
      setExtractedCost(val);
      if (budget > 0) setBudgetPct(Math.min(100, (val / budget) * 100));
    }
  }, [data, budget]);

  if (budget <= 0) return null;

  const spent = extractedCost ?? 0;
  const remaining = Math.max(0, budget - spent);
  const pct = Math.min(100, (spent / budget) * 100);

  const pctColor = pct > 90 ? "bg-red-500" : pct > 70 ? "bg-amber-500" : "bg-emerald-500";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col gap-2 w-full max-w-5xl mx-auto mb-4 px-1"
    >
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-zinc-400">
          Budget <span className="text-white font-semibold">{formatCurrency(budget, currency)}</span>
        </span>
        <span className="text-zinc-500">
          Spent <span className="text-orange-400 font-semibold">{formatCurrency(spent, currency)}</span>
        </span>
        <span className="text-zinc-500">
          Remaining <span className={remaining > 0 ? "text-emerald-400 font-semibold" : "text-red-400 font-semibold"}>{formatCurrency(remaining, currency)}</span>
        </span>
      </div>
      <div className="w-full h-1.5 bg-zinc-800/60 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: "0%" }}
          animate={{ width: `${Math.min(100, pct)}%` }}
          transition={{ duration: 1, ease: "easeOut" }}
          className={`h-full rounded-full ${pctColor}`}
        />
      </div>
      <div className="flex justify-between text-[10px] text-zinc-600">
        <span>{pct.toFixed(0)}% used</span>
        <span>{data.duration_days || "?"} day{(data.duration_days || 0) !== 1 ? "s" : ""}</span>
      </div>
    </motion.div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex justify-end mt-4">
      <button
        onClick={handleCopy}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 transition-all"
        title="Copy response"
      >
        {copied ? (
          <>
            <Check className="w-3.5 h-3.5 text-green-400" />
            <span className="text-green-400">Copied!</span>
          </>
        ) : (
          <>
            <Copy className="w-3.5 h-3.5" />
            <span>Copy</span>
          </>
        )}
      </button>
    </div>
  );
}

export default function Home() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(-1);
  const [simulationLogs, setSimulationLogs] = useState<AgentMessage[]>([]);
  const [simulationStage, setSimulationStage] = useState<"idle" | "parsing" | "agents" | "done">("idle");
  const [itineraryResult, setItineraryResult] = useState<any>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [streamingTokens, setStreamingTokens] = useState<string>("");
  const [currentAgentKey, setCurrentAgentKey] = useState<string>("");

  // Travelers state
  const [travelers, setTravelers] = useState({ adults: 1, kids: 0, infants: 0 });
  const travelersRef = useRef({ adults: 1, kids: 0, infants: 0 });
  const lastTravelersRef = useRef({ adults: 1, kids: 0, infants: 0 });

  // Trip style state
  const [tripStyle, setTripStyle] = useState("");

  // Regeneration confirmation modal
  const [showRegenModal, setShowRegenModal] = useState(false);
  const [pendingSend, setPendingSend] = useState<{
    msg: string; files?: File[]; provider: string; apiKey: string; agentProviders: Record<string, string>;
    adults: number; kids: number; infants: number; tripStyle: string;
  } | null>(null);

  // Auth
  const { user, loading: authLoading } = useAuth();

  // Session / History state
  const [sessionId] = useState(() =>
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : "session-" + Date.now()
  );
  const [showHistory, setShowHistory] = useState(false);
  const [historySessions, setHistorySessions] = useState<ChatSession[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Load Firestore sessions when user logs in
  useEffect(() => {
    if (user) {
      setHistoryLoading(true);
      fsListSessions(user)
        .then(setHistorySessions)
        .catch(() => {})
        .finally(() => setHistoryLoading(false));
    } else {
      setHistorySessions([]);
    }
  }, [user]);

  const abortControllerRef = useRef<AbortController | null>(null);

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const springConfig = { damping: 25, stiffness: 150 };
  const springX = useSpring(mouseX, springConfig);
  const springY = useSpring(mouseY, springConfig);
  const bgX = useTransform(springX, [-0.5, 0.5], ["-3%", "3%"]);
  const bgY = useTransform(springY, [-0.5, 0.5], ["-3%", "3%"]);
  const textRotateX = useTransform(springY, [-0.5, 0.5], [15, -15]);
  const textRotateY = useTransform(springX, [-0.5, 0.5], [-15, 15]);

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    mouseX.set(x);
    mouseY.set(y);
  };

  const runAgentSimulation = async (userInput: string, provider: string = "ollama", apiKey: string = "", agentProviders: Record<string, string> = {}, adults: number = 1, kids: number = 0, infants: number = 0, tripStyle: string = "") => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    let logCounter = 1;
    let isTimeout = false;
    const timeoutId = setTimeout(() => {
      isTimeout = true;
      controller.abort();
    }, 300000);
    setSimulationStage("agents");
    setIsProcessing(true);
    setStreamingTokens("");
    setSimulationLogs([
      {
        id: "init",
        agent: "Planner",
        agentKey: "supervisor_agent",
        status: "thinking",
        text: "Orchestrator parsing request: Analyzing input and preparing agent workspaces...",
        timestamp: new Date().toLocaleTimeString(),
      }
    ]);
    setActiveStep(0);
    setItineraryResult(null);

    try {
      const response = await fetch("/api/v1/plan/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          user_request: userInput, 
          stream: true,
          provider: provider,
          api_key: apiKey,
          agent_providers: Object.keys(agentProviders).length > 0 ? agentProviders : undefined,
          session_id: sessionId,
          adults: adults,
          kids: kids,
          infants: infants,
          trip_style: tripStyle,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        let done = false;
        let buffer = "";

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

                if (eventType === "start") {
                  setSimulationLogs(prev => 
                    prev.map(l => l.id === "init" ? {
                      ...l,
                      text: data.message || "TRIPZ agents initializing...",
                    } : l)
                  );
                } else if (eventType === "token") {
                  setStreamingTokens(prev => prev + data.token);
                } else if (eventType === "agent_start") {
                  setStreamingTokens("");
                  setSimulationStage("agents");
                  setCurrentAgentKey(data.agent);
                  const mapped = AGENT_MAP[data.agent] || { name: "Planner" as const, step: 0 };
                  setActiveStep(mapped.step);
                  setSimulationLogs(prev => {
                    if (data.agent === "supervisor_agent") {
                      return prev.map(l => l.id === "init" ? {
                        ...l,
                        text: data.message || "Parsing your travel request...",
                      } : l);
                    }
                    return [...prev, {
                      id: String(logCounter++),
                      agent: mapped.name,
                      agentKey: data.agent,
                      status: "thinking",
                      text: data.message || `Running ${data.agent}...`,
                      timestamp: new Date().toLocaleTimeString()
                    }];
                  });
                } else if (eventType === "agent_complete") {
                  setStreamingTokens("");
                  const mapped = AGENT_MAP[data.agent];
                  setSimulationLogs(prev => {
                    const newLogs = [...prev];
                    const targetAgent = mapped?.name;
                    for (let i = newLogs.length - 1; i >= 0; i--) {
                      if (targetAgent && newLogs[i].agent === targetAgent && newLogs[i].status === "thinking") {
                        newLogs[i].status = "completed";
                        newLogs[i].output = data.output;
                        if (data.preview && Object.keys(data.preview).length > 0) {
                          const previewText = JSON.stringify(data.preview)
                             .replace(/["{}]/g, "")
                             .replace(/:/g, ": ")
                             .replace(/,/g, " | ");
                          newLogs[i].text += ` → ${previewText}`;
                        }
                        break;
                      }
                    }
                    if (!targetAgent) {
                      const lastThinking = newLogs.findLastIndex(l => l.status === "thinking");
                      if (lastThinking >= 0) newLogs[lastThinking].status = "completed";
                    }
                    return newLogs;
                  });
                } else if (eventType === "done") {
                  setStreamingTokens("");
                  if (data.error_type) {
                    const errorMsg = formatErrorForDisplay(data.error_type, data.error);
                    setValidationError(errorMsg);
                  }
                  setItineraryResult(data);
                  setActiveStep(4);
                  setSimulationStage("done");
                  setIsProcessing(false);
                    if (!data.error_type) {
                      lastTravelersRef.current = { ...travelersRef.current };
                      // Save to Firestore if logged in
                      if (user) {
                        const title = (data.destination || userInput).slice(0, 60);
                        fsUpdateItinerary(
                          user,
                          sessionId,
                          data.itinerary || data,
                          title,
                          data.destination || "",
                          userInput,
                        ).catch((err) => console.error("Firestore save failed:", err));
                      }
                  }
                } else if (eventType === "error") {
                  setStreamingTokens("");
                  const errorMapped = AGENT_MAP[data.agent] || { name: "Planner" as const, step: 0 };
                  setSimulationLogs(prev => [...prev, {
                    id: String(logCounter++),
                    agent: errorMapped.name,
                    agentKey: data.agent || "unknown",
                    status: "completed",
                    text: data.message || "An error occurred",
                    timestamp: new Date().toLocaleTimeString(),
                    isError: true,
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
        if (isTimeout) {
          setSimulationLogs(prev => [...prev, {
            id: "timeout",
            agent: "Planner",
            agentKey: "supervisor_agent",
            status: "completed",
            text: "Request timed out after 300 seconds. The backend might be unavailable or overloaded.",
            timestamp: new Date().toLocaleTimeString(),
            isError: true,
          }]);
          const providerName = provider === "ollama" ? "Ollama (qwen2.5:1.5b)" : provider === "groq" ? "Groq (llama-3.3-70b)" : provider;
          setValidationError(`The request took too long with ${providerName}. Check that your provider is running and the API key is correct, or try a different provider in Settings.`);
          setIsProcessing(false);
          setSimulationStage("done");
        }
        return;
      }
      console.error(error);
      setSimulationLogs(prev => [...prev, {
        id: "error",
        agent: "Planner",
        agentKey: "supervisor_agent",
        status: "completed",
        text: `Network Error: Could not connect to backend.`,
        timestamp: new Date().toLocaleTimeString(),
        isError: true,
      }]);
      setIsProcessing(false);
      setSimulationStage("done");
    } finally {
      clearTimeout(timeoutId);
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
    }
  };

  const handleSend = (msg: string, files?: File[], provider: string = "ollama", apiKey: string = "", agentProviders: Record<string, string> = {}, adults: number = 1, kids: number = 0, infants: number = 0, tripStyle: string = "") => {
    if (!msg || msg.trim() === "") return;
    if (!isTripRelated(msg)) {
      setValidationError("Please type a request related to trip planning (e.g., '3 days in Tokyo', 'Paris budget route', or 'explore Rome').");
      return;
    }
    setValidationError(null);

    // Check if travelers changed and there's an existing itinerary
    const last = lastTravelersRef.current;
    const changed = last.adults !== adults || last.kids !== kids || last.infants !== infants;
    if (changed && simulationStage === "done" && itineraryResult) {
      setPendingSend({ msg, files, provider, apiKey, agentProviders, adults, kids, infants, tripStyle });
      setShowRegenModal(true);
      return;
    }

    lastTravelersRef.current = { adults, kids, infants };
    travelersRef.current = { adults, kids, infants };
    setTravelers({ adults, kids, infants });
    runAgentSimulation(msg, provider, apiKey, agentProviders, adults, kids, infants, tripStyle);
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

  const fetchSessions = useCallback(async () => {
    setHistoryLoading(true);
    try {
      if (user) {
        const sessions = await fsListSessions(user);
        setHistorySessions(sessions);
      } else {
        const res = await fetch("/api/v1/sessions");
        if (res.ok) {
          const data = await res.json();
          setHistorySessions(data.sessions || []);
        }
      }
    } catch {
      // silently fail
    } finally {
      setHistoryLoading(false);
    }
  }, [user]);

  const handleHistoryToggle = useCallback(() => {
    setShowHistory((prev) => {
      if (!prev) fetchSessions();
      return !prev;
    });
  }, [fetchSessions]);

  const handleSelectSession = useCallback(async (sid: string) => {
    try {
      if (user) {
        const session = await fsLoadSession(user, sid);
        if (session) {
          setItineraryResult({ itinerary: session.itinerary });
          setSimulationStage("done");
          setShowHistory(false);
          setActiveStep(4);
        }
      } else {
        const res = await fetch(`/api/v1/sessions/${sid}`);
        if (res.ok) {
          const data = await res.json();
          setItineraryResult({ itinerary: data.itinerary });
          setSimulationStage("done");
          setShowHistory(false);
          setActiveStep(4);
        }
      }
    } catch {
      // silently fail
    }
  }, [user]);

  const handleDeleteSession = useCallback(async (sid: string) => {
    try {
      if (user) {
        await fsDeleteSession(user, sid);
      } else {
        await fetch(`/api/v1/sessions/${sid}`, { method: "DELETE" });
      }
      setHistorySessions((prev) => prev.filter((s) => s.session_id !== sid));
    } catch {
      // silently fail
    }
  }, [user]);

  const bentoAgents = [
    { name: "Planner", icon: Compass, step: 0 },
    { name: "Budget", icon: DollarSign, step: 1 },
    { name: "Transit", icon: Plane, step: 2 },
    { name: "Curator", icon: MapPin, step: 3 },
    { name: "Synthesis", icon: Sparkles, step: 4 }
  ];

  return (
    <div 
      onMouseMove={handleMouseMove}
      className="h-screen text-[#f4f4f5] font-sans selection:bg-orange-500/30 selection:text-orange-400 relative overflow-hidden flex flex-col justify-between"
    >
      <motion.div
        className="absolute inset-[-5%] bg-[url('/bg.jpeg')] bg-cover bg-center bg-no-repeat -z-20"
        style={{ x: bgX, y: bgY }}
      />
      <div className="absolute inset-0 bg-[#09090b]/85 backdrop-blur-[3px] -z-10 pointer-events-none"></div>
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-orange-600/10 rounded-full blur-[140px] pointer-events-none -z-10 animate-pulse duration-[8000ms]"></div>
      <ShootingStarsOverlay />

      <HistorySidebar
        open={showHistory}
        onClose={() => setShowHistory(false)}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        sessions={historySessions}
        loading={historyLoading}
      />

      <div className="absolute top-0 left-0 right-0 z-30 flex items-center justify-between px-4 md:px-8 py-4">
        <div className="pointer-events-auto">
          <AnimatePresence>
            {simulationStage !== "idle" && (
              <motion.div
                layoutId="tripz-logo-container"
                initial={{ opacity: 0, y: -20, scale: 0.8 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ type: "spring", stiffness: 200, damping: 20 }}
              >
                <span className="inline-block font-kenyan italic font-black text-4xl tracking-widest text-orange-500 drop-shadow-[0_0_15px_rgba(234,88,12,0.8)]">
                  TRIPZ
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <div className="pointer-events-auto flex items-center gap-2">
          {!authLoading && <LoginButton />}
        </div>
      </div>

      <div className="flex-1 max-w-5xl w-full mx-auto flex flex-col relative z-10 h-full p-4 md:p-6 pt-20">
        <div className="flex-1 flex flex-col overflow-y-auto scrollbar-thin scrollbar-thumb-[#333] scrollbar-track-transparent py-4 min-h-0">
          <AnimatePresence mode="wait">
            {simulationStage === "idle" && (
              <motion.div
                key="idle"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9, filter: "blur(10px)" }}
                transition={{ duration: 0.4 }}
                className="flex flex-col items-center justify-center min-h-full pt-[8vh] space-y-6"
              >
                <motion.div 
                  layoutId="tripz-logo-container"
                  style={{ perspective: 1200 }}
                  className="flex items-center justify-center"
                >
                  <motion.div
                    style={{
                      rotateX: textRotateX,
                      rotateY: textRotateY,
                      transformStyle: "preserve-3d",
                    }}
                    className="relative flex items-center justify-center"
                  >
                    <span className="absolute inset-0 flex items-center justify-center font-kenyan italic font-black text-8xl md:text-[8.5rem] lg:text-[10rem] logo-base-3d leading-none text-black/55 select-none blur-[10px] text-center"
                      style={{ transform: "translateZ(-35px) translateY(8px)" }}>
                      TRIPZ
                    </span>
                    <span className="absolute inset-0 flex items-center justify-center font-kenyan italic font-black text-8xl md:text-[8.5rem] lg:text-[10rem] logo-base-3d leading-none text-orange-950 select-none blur-[6px] text-center"
                      style={{ transform: "translateZ(-20px)" }}>
                      TRIPZ
                    </span>
                    <span className="absolute inset-0 flex items-center justify-center font-kenyan italic font-black text-8xl md:text-[8.5rem] lg:text-[10rem] logo-base-3d leading-none text-orange-800 select-none text-center"
                      style={{ transform: "translateZ(-8px)" }}>
                      TRIPZ
                    </span>
                    <h1 className="font-kenyan italic font-black text-8xl md:text-[8.5rem] lg:text-[10rem] logo-base-3d select-none retro-text leading-none relative z-10 text-center"
                      style={{ transform: "translateZ(25px)" }}>
                      TRIPZ
                    </h1>
                  </motion.div>
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
                className="flex flex-col items-center justify-center min-h-full"
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
                className="flex flex-col items-center w-full space-y-6 pr-2 pb-10"
              >
                <div className="flex items-stretch justify-center gap-6 flex-shrink-0 w-full max-w-5xl mx-auto py-4">
                  {bentoAgents.map((agent, i) => {
                    const logs = simulationLogs.filter(l => l.agent === agent.name);
                    const hasError = logs.some(l => l.isError === true);
                    const isThinking = logs.some(l => l.status === "thinking");
                    
                    const isCompleted = logs.length > 0 && logs.every(l => l.status === "completed") && !isThinking;
                    const isActive = isThinking;
                    const isPending = logs.length === 0;
                    const activeLog = logs.find(l => l.status === "thinking");
                    const cardAgentKey = activeLog?.agentKey || currentAgentKey;
                    
                    return (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{
                          opacity: 1,
                          scale: 1,
                          transition: { delay: i * 0.1 }
                        }}
                        className={`relative overflow-hidden flex flex-col p-5 rounded-2xl border transition-all duration-500 flex-1 min-w-0 ${
                          hasError
                            ? "border-red-500/50 bg-red-950/20 shadow-[0_0_20px_rgba(239,68,68,0.15)]"
                            : isActive
                              ? "border-orange-500/50 bg-orange-950/20 shadow-[0_0_20px_rgba(234,88,12,0.15)]"
                              : isCompleted
                                ? "border-emerald-500/30 bg-emerald-950/10 shadow-[0_0_15px_rgba(16,185,129,0.05)]"
                                : "border-zinc-800/40 bg-zinc-950/40 opacity-60"
                        } backdrop-blur-md min-h-[8rem] h-auto`}
                      >
                        <div className="flex items-center justify-between mb-3 shrink-0">
                          <div className="flex items-center gap-2 min-w-0">
                            <div className={`p-2 rounded-xl transition-colors duration-500 shrink-0 ${
                              hasError
                                ? 'bg-red-500/20 text-red-400'
                                : isActive
                                  ? 'bg-orange-500/20 text-orange-400 animate-pulse'
                                  : isCompleted
                                    ? 'bg-emerald-500/20 text-emerald-400'
                                    : 'bg-zinc-900 text-zinc-600'
                            }`}>
                              <agent.icon className="h-4.5 w-4.5" />
                            </div>
                            <span className={`font-bold tracking-wide text-xs md:text-sm truncate transition-colors duration-500 ${
                              hasError
                                ? 'text-red-300'
                                : isActive || isCompleted
                                  ? 'text-white'
                                  : 'text-zinc-500'
                            }`}>{agent.name}</span>
                          </div>
                          {hasError && <div className="h-2 w-2 rounded-full bg-red-500 animate-ping" />}
                          {isActive && !hasError && <Loader2 className="h-4 w-4 text-orange-500 animate-spin" />}
                          {isCompleted && !hasError && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
                        </div>

                        <div className="flex-1 text-xs md:text-[13px] text-zinc-400 font-mono flex flex-col justify-center min-w-0 overflow-hidden">
                          {hasError ? (
                            <span className="text-red-400 font-semibold text-[11px] md:text-[12px] leading-relaxed line-clamp-2 break-words">{logs.find(l => l.isError)?.text || "Error"}</span>
                          ) : isCompleted ? (
                            <AgentOutputCard log={logs[logs.length - 1]} />
                          ) : isPending ? (
                            <span className="text-zinc-600 italic">Waiting...</span>
                          ) : isActive ? (
                            <motion.div
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              className="flex flex-col gap-1 h-full overflow-hidden"
                            >
                              <span className="text-orange-400/80 text-[11px] md:text-[12px] leading-relaxed font-mono">
                                <TypingMessage agentKey={cardAgentKey} />
                              </span>
                              {streamingTokens ? (
                                <span className="text-zinc-500 text-[10px] md:text-[11px] leading-normal mt-1 overflow-y-auto line-clamp-2 break-words">
                                  {streamingTokens}
                                </span>
                              ) : null}
                            </motion.div>
                          ) : null}
                        </div>

                        {isActive && (
                          <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-orange-500 to-transparent animate-pulse" />
                        )}
                        {isCompleted && (
                          <motion.div
                            initial={{ width: "0%" }}
                            animate={{ width: "100%" }}
                            transition={{ duration: 0.5 }}
                            className="absolute bottom-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent"
                          />
                        )}
                      </motion.div>
                    );
                  })}
                </div>

                <AnimatePresence>
                  {simulationStage === "done" && itineraryResult && itineraryResult.error_type && (
                    <motion.div
                      initial={{ opacity: 0, y: 30, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ duration: 0.6, type: "spring", bounce: 0.4 }}
                      className="flex gap-4 w-full max-w-4xl mx-auto flex-shrink-0"
                    >
                      <div className="w-8 h-8 rounded-full bg-red-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-red-600/20 mt-1">
                        <Bot className="w-4 h-4 text-white" />
                      </div>
                      <div className="flex-1 bg-zinc-900/60 p-6 rounded-3xl border border-red-800/40 backdrop-blur-md">
                        <div className="flex flex-col items-center py-8 text-center">
                          <div className="text-3xl mb-3">{itineraryResult.error_type === "quota_exceeded" ? "⚠️" : "📏"}</div>
                          <p className="text-red-400 font-semibold mb-1">
                            {itineraryResult.error_type === "quota_exceeded" ? "API Rate Limit Reached" : "Token Limit Exceeded"}
                          </p>
                          <p className="text-zinc-400 text-xs max-w-sm">{itineraryResult.error}</p>
                          <p className="text-zinc-500 text-xs mt-4">Try switching to a different provider in Settings, or wait before retrying.</p>
                        </div>
                      </div>
                    </motion.div>
                  )}
                  {simulationStage === "done" && itineraryResult && !itineraryResult.error_type && (
                    <motion.div
                      initial={{ opacity: 0, y: 30, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ duration: 0.6, type: "spring", bounce: 0.4 }}
                      className="w-full flex-shrink-0"
                    >
                      {itineraryResult.itinerary?.markdown ? (
                        <div className="flex flex-col gap-4 w-full max-w-5xl mx-auto">
                          <BudgetIndicator data={itineraryResult} />
                          <div className="flex gap-4">
                            <div className="w-8 h-8 rounded-full bg-orange-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-orange-600/20 mt-1">
                              <Bot className="w-4 h-4 text-white" />
                            </div>
                            <div className="flex-1 bg-zinc-900/60 p-6 rounded-3xl border border-zinc-800/60 backdrop-blur-md text-sm text-zinc-300">
                              <div className="prose prose-invert prose-sm max-w-none
                                prose-headings:text-orange-400 prose-headings:font-bold
                                prose-h1:text-2xl prose-h1:mb-4 prose-h1:mt-2
                                prose-h2:text-xl prose-h2:mb-3 prose-h2:mt-4
                                prose-h3:text-lg prose-h3:mb-2 prose-h3:mt-3
                                prose-strong:text-orange-300 prose-strong:font-semibold
                                prose-ul:list-disc prose-ul:pl-5 prose-ul:space-y-1
                                prose-li:marker:text-orange-500
                                prose-p:leading-relaxed prose-p:mb-2
                                prose-hr:border-zinc-700 prose-hr:my-4
                                prose-code:text-orange-200 prose-code:bg-zinc-800 prose-code:px-1 prose-code:rounded
                                prose-pre:bg-zinc-800 prose-pre:border prose-pre:border-zinc-700">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                  {itineraryResult.itinerary.markdown}
                                </ReactMarkdown>
                              </div>
                              <CopyButton text={itineraryResult.itinerary.markdown} />
                            </div>
                          </div>
                        </div>
                      ) : (
                        <ItineraryBoard itinerary={itineraryResult.itinerary} warnings={itineraryResult.warnings} duration_ms={itineraryResult.duration_ms} />
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

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
            showHistory={showHistory}
            onHistoryToggle={handleHistoryToggle}
            adults={travelers.adults}
            kids={travelers.kids}
            infants={travelers.infants}
            tripStyle={tripStyle}
            onTravelersChange={(a, k, i) => setTravelers({ adults: a, kids: k, infants: i })}
            onTripStyleChange={(s) => setTripStyle(s)}
          />
          <div className="text-[10px] text-white-500 text-center mt-3 flex items-center justify-center gap-1 opacity-70">
            <Sparkles className="h-3 w-3 text-orange-500" />
            <span>Multi-Agent debate triggers automatically upon input.</span>
          </div>
        </div>
      </div>

      {/* Regeneration confirmation modal */}
      {showRegenModal && pendingSend && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#1F2023] border border-[#333333] rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl">
            <h3 className="text-lg font-semibold text-white mb-3">Travelers Changed</h3>
            <p className="text-sm text-zinc-400 mb-6">
              The number of travelers changed from {lastTravelersRef.current.adults}A {lastTravelersRef.current.kids}K {lastTravelersRef.current.infants}I to {pendingSend.adults}A {pendingSend.kids}K {pendingSend.infants}I.
              Regenerate the trip with the new traveler count?
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowRegenModal(false);
                  setPendingSend(null);
                }}
                className="px-4 py-2 text-sm text-zinc-400 bg-zinc-800/60 hover:bg-zinc-700/60 rounded-xl transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowRegenModal(false);
                  const p = pendingSend!;
                  lastTravelersRef.current = { adults: p.adults, kids: p.kids, infants: p.infants };
                  travelersRef.current = { adults: p.adults, kids: p.kids, infants: p.infants };
                  setTravelers({ adults: p.adults, kids: p.kids, infants: p.infants });
                  setPendingSend(null);
                  runAgentSimulation(p.msg, p.provider, p.apiKey, p.agentProviders, p.adults, p.kids, p.infants, p.tripStyle);
                }}
                className="px-4 py-2 text-sm text-white bg-orange-600 hover:bg-orange-500 rounded-xl transition-all"
              >
                Regenerate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
