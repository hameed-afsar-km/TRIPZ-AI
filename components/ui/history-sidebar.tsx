"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { History, X, Clock, MapPin, Trash2, ExternalLink } from "lucide-react";

interface SessionSummary {
  session_id: string;
  title: string;
  destination: string;
  timestamp: number;
}

interface HistorySidebarProps {
  open: boolean;
  onClose: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  sessions: SessionSummary[];
  loading?: boolean;
}

export const HistorySidebar: React.FC<HistorySidebarProps> = ({
  open,
  onClose,
  onSelectSession,
  onDeleteSession,
  sessions,
  loading = false,
}) => {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 z-40"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed top-0 left-0 bottom-0 w-80 max-w-[85vw] z-50 bg-[#121212]/95 backdrop-blur-2xl border-r border-white/10 shadow-2xl flex flex-col"
          >
            <div className="flex items-center justify-between p-4 border-b border-white/10 shrink-0">
              <div className="flex items-center gap-2">
                <History className="h-5 w-5 text-orange-400" />
                <h2 className="text-lg font-bold text-white">History</h2>
              </div>
              <button
                onClick={onClose}
                className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-white/10 transition-colors text-gray-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-thin scrollbar-thumb-[#333] scrollbar-track-transparent">
              {loading && (
                <div className="flex items-center justify-center py-12">
                  <div className="h-5 w-5 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
                </div>
              )}

              {!loading && sessions.length === 0 && (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <History className="h-10 w-10 text-gray-600 mb-3" />
                  <p className="text-sm text-gray-500">No past trips yet</p>
                  <p className="text-xs text-gray-600 mt-1">Your generated itineraries will appear here</p>
                </div>
              )}

              {!loading &&
                sessions.map((session) => (
                  <motion.div
                    key={session.session_id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="group relative bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] hover:border-white/[0.12] rounded-xl p-3.5 cursor-pointer transition-all duration-200"
                    onClick={() => onSelectSession(session.session_id)}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <h3 className="text-sm font-semibold text-white truncate">
                          {session.title}
                        </h3>
                        <div className="flex items-center gap-1.5 mt-1.5">
                          <MapPin className="h-3 w-3 text-orange-400 shrink-0" />
                          <span className="text-xs text-gray-400 truncate">
                            {session.destination}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 mt-1">
                          <Clock className="h-3 w-3 text-gray-500 shrink-0" />
                          <span className="text-[11px] text-gray-500">
                            {new Date(session.timestamp * 1000).toLocaleDateString(undefined, {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectSession(session.session_id);
                          }}
                          className="h-7 w-7 flex items-center justify-center rounded-lg text-gray-500 hover:text-orange-400 hover:bg-white/10 transition-all opacity-0 group-hover:opacity-100"
                          title="View"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteSession(session.session_id);
                          }}
                          className="h-7 w-7 flex items-center justify-center rounded-lg text-gray-500 hover:text-red-400 hover:bg-white/10 transition-all opacity-0 group-hover:opacity-100"
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </motion.div>
                ))}
            </div>

            <div className="p-3 border-t border-white/10 shrink-0">
              <p className="text-[10px] text-gray-600 text-center">
                Sessions expire after 30 minutes
              </p>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
};
