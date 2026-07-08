"use client";

import React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ArrowUp, Paperclip, Square, X, StopCircle, Mic, History, Settings } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// Utility function for className merging
const cn = (...classes: (string | undefined | null | false)[]) => classes.filter(Boolean).join(" ");

// Embedded CSS for minimal custom styles
const styles = `
  *:focus-visible {
    outline-offset: 0 !important;
    --ring-offset: 0 !important;
  }
  textarea::-webkit-scrollbar {
    width: 6px;
  }
  textarea::-webkit-scrollbar-track {
    background: transparent;
  }
  textarea::-webkit-scrollbar-thumb {
    background-color: #444444;
    border-radius: 3px;
  }
  textarea::-webkit-scrollbar-thumb:hover {
    background-color: #555555;
  }
`;

// Inject styles into document (client-side only)
if (typeof window !== "undefined") {
  const styleSheet = document.createElement("style");
  styleSheet.innerText = styles;
  document.head.appendChild(styleSheet);
}

// Textarea Component
interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  className?: string;
}
const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, ...props }, ref) => (
  <textarea
    className={cn(
      "flex w-full rounded-md border-none bg-transparent px-3 py-3.5 text-base text-gray-100 placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed disabled:opacity-50 min-h-[64px] resize-none scrollbar-thin scrollbar-thumb-[#444444] scrollbar-track-transparent hover:scrollbar-thumb-[#555555]",
      className
    )}
    ref={ref}
    rows={1}
    {...props}
  />
));
Textarea.displayName = "Textarea";

// Tooltip Components
const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;
const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      "z-50 overflow-hidden rounded-md border border-[#333333] bg-[#1F2023] px-3 py-1.5 text-sm text-white shadow-md animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
      className
    )}
    {...props}
  />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

// Dialog Components
const Dialog = DialogPrimitive.Root;
const DialogPortal = DialogPrimitive.Portal;
const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-[90vw] md:max-w-[800px] translate-x-[-50%] translate-y-[-50%] gap-4 border border-[#333333] bg-[#1F2023] p-0 shadow-xl duration-300 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 rounded-2xl",
        className
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 z-10 rounded-full bg-[#2E3033]/80 p-2 hover:bg-[#2E3033] transition-all">
        <X className="h-5 w-5 text-gray-200 hover:text-white" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight text-gray-100", className)}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

// Button Component
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
}
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    const variantClasses = {
      default: "bg-white hover:bg-white/80 text-black",
      outline: "border border-[#444444] bg-transparent hover:bg-[#3A3A40]",
      ghost: "bg-transparent hover:bg-[#3A3A40]",
    };
    const sizeClasses = {
      default: "h-10 px-4 py-2",
      sm: "h-8 px-3 text-sm",
      lg: "h-12 px-6",
      icon: "h-8 w-8 rounded-full aspect-[1/1]",
    };
    return (
      <button
        className={cn(
          "inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

// VoiceRecorder Component
interface VoiceRecorderProps {
  isRecording: boolean;
  onStartRecording: () => void;
  onStopRecording: (duration: number) => void;
  visualizerBars?: number;
}
const VoiceRecorder: React.FC<VoiceRecorderProps> = ({
  isRecording,
  onStartRecording,
  onStopRecording,
  visualizerBars = 32,
}) => {
  const [time, setTime] = React.useState(0);
  const timerRef = React.useRef<NodeJS.Timeout | null>(null);

  React.useEffect(() => {
    if (isRecording) {
      onStartRecording();
      timerRef.current = setInterval(() => setTime((t) => t + 1), 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      onStopRecording(time);
      setTime(0);
    }
    return () => {
      if (timerRef.current) {
        if (timerRef.current) clearInterval(timerRef.current);
      }
    };
  }, [isRecording, onStartRecording, onStopRecording]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center w-full transition-all duration-300 py-3",
        isRecording ? "opacity-100" : "opacity-0 h-0"
      )}
    >
      <div className="flex items-center gap-2 mb-3">
        <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
        <span className="font-mono text-sm text-white/80">{formatTime(time)}</span>
      </div>
      <div className="w-full h-10 flex items-center justify-center gap-0.5 px-4">
        {[...Array(visualizerBars)].map((_, i) => (
          <div
            key={i}
            className="w-0.5 rounded-full bg-white/50 animate-pulse"
            style={{
              height: `${Math.max(15, Math.random() * 100)}%`,
              animationDelay: `${i * 0.05}s`,
              animationDuration: `${0.5 + Math.random() * 0.5}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
};

// ImageViewDialog Component
interface ImageViewDialogProps {
  imageUrl: string | null;
  onClose: () => void;
}
const ImageViewDialog: React.FC<ImageViewDialogProps> = ({ imageUrl, onClose }) => {
  if (!imageUrl) return null;
  return (
    <Dialog open={!!imageUrl} onOpenChange={onClose}>
      <DialogContent className="p-0 border-none bg-transparent shadow-none max-w-[90vw] md:max-w-[800px]">
        <DialogTitle className="sr-only">Image Preview</DialogTitle>
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="relative bg-[#1F2023] rounded-2xl overflow-hidden shadow-2xl"
        >
          <img
            src={imageUrl}
            alt="Full preview"
            className="w-full max-h-[80vh] object-contain rounded-2xl"
          />
        </motion.div>
      </DialogContent>
    </Dialog>
  );
};

// PromptInput Context and Components
interface PromptInputContextType {
  isLoading: boolean;
  value: string;
  setValue: (value: string) => void;
  maxHeight: number | string;
  onSubmit?: () => void;
  disabled?: boolean;
}
const PromptInputContext = React.createContext<PromptInputContextType>({
  isLoading: false,
  value: "",
  setValue: () => {},
  maxHeight: 240,
  onSubmit: undefined,
  disabled: false,
});
function usePromptInput() {
  const context = React.useContext(PromptInputContext);
  if (!context) throw new Error("usePromptInput must be used within a PromptInput");
  return context;
}

interface PromptInputProps {
  isLoading?: boolean;
  value?: string;
  onValueChange?: (value: string) => void;
  maxHeight?: number | string;
  onSubmit?: () => void;
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
  onDragOver?: (e: React.DragEvent) => void;
  onDragLeave?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
}
const PromptInput = React.forwardRef<HTMLDivElement, PromptInputProps>(
  (
    {
      className,
      isLoading = false,
      maxHeight = 240,
      value,
      onValueChange,
      onSubmit,
      children,
      disabled = false,
      onDragOver,
      onDragLeave,
      onDrop,
    },
    ref
  ) => {
    const [internalValue, setInternalValue] = React.useState(value || "");
    const handleChange = (newValue: string) => {
      setInternalValue(newValue);
      onValueChange?.(newValue);
    };
    return (
      <TooltipProvider>
        <PromptInputContext.Provider
          value={{
            isLoading,
            value: value ?? internalValue,
            setValue: onValueChange ?? handleChange,
            maxHeight,
            onSubmit,
            disabled,
          }}
        >
          <div
            ref={ref}
            className={cn(
              "rounded-3xl border border-white/15 bg-zinc-950/25 backdrop-blur-lg p-2 shadow-[0_8px_32px_0_rgba(0,0,0,0.5)] transition-all duration-300",
              isLoading && "border-red-500/70",
              className
            )}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            {children}
          </div>
        </PromptInputContext.Provider>
      </TooltipProvider>
    );
  }
);
PromptInput.displayName = "PromptInput";

interface PromptInputTextareaProps {
  disableAutosize?: boolean;
  placeholder?: string;
}
const PromptInputTextarea: React.FC<PromptInputTextareaProps & React.ComponentProps<typeof Textarea>> = ({
  className,
  onKeyDown,
  disableAutosize = false,
  placeholder,
  ...props
}) => {
  const { value, setValue, maxHeight, onSubmit, disabled } = usePromptInput();
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    if (disableAutosize || !textareaRef.current) return;
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height =
      typeof maxHeight === "number"
        ? `${Math.min(textareaRef.current.scrollHeight, maxHeight)}px`
        : `min(${textareaRef.current.scrollHeight}px, ${maxHeight})`;
  }, [value, maxHeight, disableAutosize]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit?.();
    }
    onKeyDown?.(e);
  };

  return (
    <Textarea
      ref={textareaRef}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      className={cn("text-base", className)}
      disabled={disabled}
      placeholder={placeholder}
      {...props}
    />
  );
};

interface PromptInputActionsProps extends React.HTMLAttributes<HTMLDivElement> {}
const PromptInputActions: React.FC<PromptInputActionsProps> = ({ children, className, ...props }) => (
  <div className={cn("flex items-center gap-2", className)} {...props}>
    {children}
  </div>
);

interface PromptInputActionProps extends React.ComponentProps<typeof Tooltip> {
  tooltip: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
}
const PromptInputAction: React.FC<PromptInputActionProps> = ({
  tooltip,
  children,
  className,
  side = "top",
  ...props
}) => {
  const { disabled } = usePromptInput();
  return (
    <Tooltip {...props}>
      <TooltipTrigger asChild disabled={disabled}>
        {children}
      </TooltipTrigger>
      <TooltipContent side={side} className={className}>
        {tooltip}
      </TooltipContent>
    </Tooltip>
  );
};

// Custom Divider Component
const CustomDivider: React.FC = () => (
  <div className="relative h-6 w-[1.5px] mx-1">
    <div
      className="absolute inset-0 bg-gradient-to-t from-transparent via-[#f97316]/70 to-transparent rounded-full"
      style={{
        clipPath: "polygon(0% 0%, 100% 0%, 100% 40%, 140% 50%, 100% 60%, 100% 100%, 0% 100%, 0% 60%, -40% 50%, 0% 40%)",
      }}
    />
  </div>
);

// Main PromptInputBox Component
interface PromptInputBoxProps {
  onSend?: (message: string, files?: File[], provider?: string, apiKey?: string, agentProviders?: Record<string, string>, adults?: number, kids?: number, infants?: number, tripStyle?: string) => void;
  onStop?: () => void;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
  showHistory?: boolean;
  onHistoryToggle?: () => void;
  adults?: number;
  kids?: number;
  infants?: number;
  tripStyle?: string;
  onTravelersChange?: (adults: number, kids: number, infants: number) => void;
  onTripStyleChange?: (style: string) => void;
}
export const PromptInputBox = React.forwardRef((props: PromptInputBoxProps, ref: React.Ref<HTMLDivElement>) => {
  const { onSend = () => {}, onStop = () => {}, isLoading = false, placeholder = "Type your message here...", className, showHistory = false, onHistoryToggle = () => {} } = props;
  const [input, setInput] = React.useState("");
  const [files, setFiles] = React.useState<File[]>([]);
  const [filePreviews, setFilePreviews] = React.useState<{ [key: string]: string }>({});
  const [selectedImage, setSelectedImage] = React.useState<string | null>(null);
  const [isRecording, setIsRecording] = React.useState(false);
  const [adults, setAdults] = React.useState(props.adults ?? 1);
  const [kids, setKids] = React.useState(props.kids ?? 0);
  const [infants, setInfants] = React.useState(props.infants ?? 0);
  const [tripStyle, setTripStyle] = React.useState(props.tripStyle || "");
  
  // Settings State
  const [showSettings, setShowSettings] = React.useState(false);
  const [provider, setProvider] = React.useState("ollama");
  const [apiKey, setApiKey] = React.useState("");
  const [freeTier, setFreeTier] = React.useState(true);

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const savedProvider = localStorage.getItem("tripz_provider");
      const savedKey = localStorage.getItem("tripz_api_key");
      const savedFreeTier = localStorage.getItem("tripz_free_tier");
      if (savedProvider) setProvider(savedProvider);
      if (savedKey) setApiKey(savedKey);
      if (savedFreeTier !== null) setFreeTier(savedFreeTier === "true");
    }
  }, []);

  const agentProviders: Record<string, string> = {};

  const saveSettings = () => {
    localStorage.setItem("tripz_provider", provider);
    localStorage.setItem("tripz_api_key", apiKey);
    localStorage.setItem("tripz_free_tier", String(freeTier));
    setShowSettings(false);
  };

  const promptBoxRef = React.useRef<HTMLDivElement>(null);
  const uploadInputRef = React.useRef<HTMLInputElement>(null);

  React.useImperativeHandle(ref, () => promptBoxRef.current as HTMLDivElement);

  const isImageFile = (file: File) => file.type.startsWith("image/");

  const processFile = (file: File) => {
    if (!isImageFile(file)) {
      console.log("Only image files are allowed");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      console.log("File too large (max 10MB)");
      return;
    }
    setFiles([file]);
    const reader = new FileReader();
    reader.onload = (e) => setFilePreviews({ [file.name]: e.target?.result as string });
    reader.readAsDataURL(file);
  };

  const handleDragOver = React.useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragLeave = React.useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = React.useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const files = Array.from(e.dataTransfer.files);
    const imageFiles = files.filter((file) => isImageFile(file));
    if (imageFiles.length > 0) processFile(imageFiles[0]);
  }, []);

  const handleRemoveFile = (index: number) => {
    const fileToRemove = files[index];
    if (fileToRemove && filePreviews[fileToRemove.name]) setFilePreviews({});
    setFiles([]);
  };

  const openImageModal = (imageUrl: string) => setSelectedImage(imageUrl);

  const handlePaste = React.useCallback((e: ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf("image") !== -1) {
        const file = items[i].getAsFile();
        if (file) {
          e.preventDefault();
          processFile(file);
          break;
        }
      }
    }
  }, []);

  React.useEffect(() => {
    document.addEventListener("paste", handlePaste);
    return () => document.removeEventListener("paste", handlePaste);
  }, [handlePaste]);

  React.useEffect(() => {
    setAdults(props.adults ?? 1);
    setKids(props.kids ?? 0);
    setInfants(props.infants ?? 0);
  }, [props.adults, props.kids, props.infants]);

  const handleTravelersChange = (type: "adults" | "kids" | "infants", delta: number) => {
    let a = adults, k = kids, i = infants;
    if (type === "adults") a = Math.max(1, a + delta);
    else if (type === "kids") k = Math.max(0, k + delta);
    else if (type === "infants") i = Math.max(0, i + delta);
    setAdults(a); setKids(k); setInfants(i);
    props.onTravelersChange?.(a, k, i);
  };

  const handleSubmit = () => {
    if (input.trim() || files.length > 0) {
      onSend(input, files, provider, apiKey, agentProviders, adults, kids, infants, tripStyle);
      setInput("");
      setFiles([]);
      setFilePreviews({});
    }
  };

  const handleStartRecording = () => console.log("Started recording");

  const handleStopRecording = (duration: number) => {
    console.log(`Stopped recording after ${duration} seconds`);
    setIsRecording(false);
    onSend(`[Voice message - ${duration} seconds]`, [], provider, apiKey, agentProviders, adults, kids, infants, tripStyle);
  };

  const hasContent = input.trim() !== "" || files.length > 0;

  return (
    <>
      <PromptInput
        value={input}
        onValueChange={setInput}
        isLoading={isLoading}
        onSubmit={handleSubmit}
        className={cn(
          "w-full bg-zinc-950/25 border border-white/15 backdrop-blur-lg shadow-[0_8px_32px_0_rgba(0,0,0,0.5)] transition-all duration-300 ease-in-out",
          isRecording && "border-red-500/70",
          className
        )}
        disabled={isLoading || isRecording}
        ref={promptBoxRef}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {files.length > 0 && !isRecording && (
          <div className="flex flex-wrap gap-2 p-0 pb-1 transition-all duration-300">
            {files.map((file, index) => (
              <div key={index} className="relative group">
                {file.type.startsWith("image/") && filePreviews[file.name] && (
                  <div
                    className="w-16 h-16 rounded-xl overflow-hidden cursor-pointer transition-all duration-300"
                    onClick={() => openImageModal(filePreviews[file.name])}
                  >
                    <img
                      src={filePreviews[file.name]}
                      alt={file.name}
                      className="h-full w-full object-cover"
                    />
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveFile(index);
                      }}
                      className="absolute top-1 right-1 rounded-full bg-black/70 p-0.5 opacity-100 transition-opacity"
                    >
                      <X className="h-3 w-3 text-white" />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div
          className={cn(
            "transition-all duration-300",
            isRecording ? "h-0 overflow-hidden opacity-0" : "opacity-100"
          )}
        >
          <PromptInputTextarea
            placeholder={
              showHistory
                ? "Searching history..."
                : placeholder
            }
            className="text-base"
          />
        </div>

        {isRecording && (
          <VoiceRecorder
            isRecording={isRecording}
            onStartRecording={handleStartRecording}
            onStopRecording={handleStopRecording}
          />
        )}

        {/* Travelers selector */}
        {!isRecording && (
          <div className="flex items-center gap-3 px-1 py-1.5">
            <span className="text-[11px] text-zinc-500 font-medium uppercase tracking-wider">Travelers</span>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-zinc-400 w-9">Adults</span>
                <button
                  onClick={() => handleTravelersChange("adults", -1)}
                  disabled={adults <= 1}
                  className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-800/60 text-zinc-400 hover:bg-zinc-700/60 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed text-xs transition-all"
                >−</button>
                <span className="text-xs text-white font-medium w-4 text-center">{adults}</span>
                <button
                  onClick={() => handleTravelersChange("adults", 1)}
                  disabled={adults >= 9}
                  className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-800/60 text-zinc-400 hover:bg-zinc-700/60 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed text-xs transition-all"
                >+</button>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-zinc-400 w-7">Kids</span>
                <button
                  onClick={() => handleTravelersChange("kids", -1)}
                  disabled={kids <= 0}
                  className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-800/60 text-zinc-400 hover:bg-zinc-700/60 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed text-xs transition-all"
                >−</button>
                <span className="text-xs text-white font-medium w-4 text-center">{kids}</span>
                <button
                  onClick={() => handleTravelersChange("kids", 1)}
                  disabled={kids >= 9}
                  className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-800/60 text-zinc-400 hover:bg-zinc-700/60 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed text-xs transition-all"
                >+</button>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-zinc-400 w-12">Infants</span>
                <button
                  onClick={() => handleTravelersChange("infants", -1)}
                  disabled={infants <= 0}
                  className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-800/60 text-zinc-400 hover:bg-zinc-700/60 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed text-xs transition-all"
                >−</button>
                <span className="text-xs text-white font-medium w-4 text-center">{infants}</span>
                <button
                  onClick={() => handleTravelersChange("infants", 1)}
                  disabled={infants >= 9}
                  className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-800/60 text-zinc-400 hover:bg-zinc-700/60 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed text-xs transition-all"
                >+</button>
              </div>
            </div>
          </div>
        )}

        {/* Trip Style selector */}
        {!isRecording && (
          <div className="flex items-center gap-3 px-1 py-1.5">
            <span className="text-[11px] text-zinc-500 font-medium uppercase tracking-wider">Style</span>
            <div className="flex items-center gap-1.5">
              {["standard", "budget", "luxury"].map((style) => (
                <button
                  key={style}
                  onClick={() => {
                    setTripStyle(style);
                    props.onTripStyleChange?.(style);
                  }}
                  className={`text-[11px] px-2.5 py-1 rounded-full border transition-all ${
                    tripStyle === style
                      ? "bg-orange-500/20 border-orange-400/50 text-orange-300"
                      : "bg-zinc-800/40 border-zinc-700/40 text-zinc-400 hover:border-zinc-600"
                  }`}
                >
                  {style === "standard" ? "Standard" : style === "budget" ? "Budget" : "Luxury"}
                </button>
              ))}
            </div>
          </div>
        )}

        <PromptInputActions className="flex items-center justify-between gap-2 p-0 pt-2">
          <div
            className={cn(
              "flex items-center gap-1 transition-opacity duration-300",
              isRecording ? "opacity-0 invisible h-0" : "opacity-100 visible"
            )}
          >
            <PromptInputAction tooltip="Upload image">
              <button
                onClick={() => uploadInputRef.current?.click()}
                className="flex h-8 w-8 text-[#9CA3AF] cursor-pointer items-center justify-center rounded-full transition-colors hover:bg-gray-600/30 hover:text-[#D1D5DB]"
                disabled={isRecording}
              >
                <Paperclip className="h-5 w-5 transition-colors" />
                <input
                  ref={uploadInputRef}
                  type="file"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files.length > 0) processFile(e.target.files[0]);
                    if (e.target) e.target.value = "";
                  }}
                  accept="image/*"
                />
              </button>
            </PromptInputAction>

            <PromptInputAction tooltip="Settings">
              <button
                type="button"
                onClick={() => setShowSettings(true)}
                className="flex h-8 w-8 text-[#9CA3AF] cursor-pointer items-center justify-center rounded-full transition-colors hover:bg-gray-600/30 hover:text-[#D1D5DB]"
                disabled={isRecording}
              >
                <Settings className="h-5 w-5 transition-colors" />
              </button>
            </PromptInputAction>

            {/* Free Tier badge */}
            <PromptInputAction
              tooltip={
                freeTier
                  ? "Free Tier ON — Groq + Gemini (no API keys needed)"
                  : "Free Tier OFF — click to use built-in free providers"
              }
            >
              <button
                type="button"
                onClick={() => setFreeTier(!freeTier)}
                className={cn(
                  "flex h-6 cursor-pointer items-center gap-1 rounded-full border px-2 text-[10px] font-semibold uppercase tracking-wider transition-all",
                  freeTier
                    ? "border-emerald-500/50 bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25"
                    : "border-zinc-700/40 bg-zinc-800/40 text-zinc-500 hover:border-zinc-600 hover:text-zinc-400"
                )}
                disabled={isRecording}
              >
                <span className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  freeTier ? "bg-emerald-400" : "bg-zinc-500"
                )} />
                Free
              </button>
            </PromptInputAction>

            <div className="flex items-center">
              <PromptInputAction tooltip="History">
                <button
                  type="button"
                  onClick={onHistoryToggle}
                  className={cn(
                    "rounded-full transition-all flex items-center gap-1 px-2 py-1 border h-8",
                    showHistory
                      ? "bg-[#1EAEDB]/15 border-[#1EAEDB] text-[#1EAEDB]"
                      : "bg-transparent border-transparent text-[#9CA3AF] hover:text-[#D1D5DB]"
                  )}
                >
                  <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
                    <motion.div
                      animate={{ rotate: showHistory ? -360 : 0, scale: showHistory ? 1.1 : 1 }}
                      whileHover={{ rotate: showHistory ? -360 : -15, scale: 1.1, transition: { type: "spring", stiffness: 300, damping: 10 } }}
                      transition={{ type: "spring", stiffness: 260, damping: 25 }}
                    >
                      <History className={cn("w-4 h-4", showHistory ? "text-[#1EAEDB]" : "text-inherit")} />
                    </motion.div>
                  </div>
                  <AnimatePresence>
                    {showHistory && (
                      <motion.span
                        initial={{ width: 0, opacity: 0 }}
                        animate={{ width: "auto", opacity: 1 }}
                        exit={{ width: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="text-xs overflow-hidden whitespace-nowrap text-[#1EAEDB] flex-shrink-0"
                      >
                        History
                      </motion.span>
                    )}
                  </AnimatePresence>
                </button>
              </PromptInputAction>
            </div>
          </div>

          <PromptInputAction
            tooltip={
              isLoading
                ? "Stop generation"
                : isRecording
                ? "Stop recording"
                : hasContent
                ? "Send message"
                : "Voice message"
            }
          >
            <Button
              variant="default"
              size="icon"
              className={cn(
                "h-8 w-8 rounded-full transition-all duration-200",
                isRecording
                  ? "bg-transparent hover:bg-gray-600/30 text-red-500 hover:text-red-400"
                  : hasContent
                  ? "bg-white hover:bg-white/80 text-[#1F2023]"
                  : "bg-transparent hover:bg-gray-600/30 text-[#9CA3AF] hover:text-[#D1D5DB]"
              )}
              onClick={() => {
                if (isLoading) onStop();
                else if (isRecording) setIsRecording(false);
                else if (hasContent) handleSubmit();
                else setIsRecording(true);
              }}
              disabled={false}
            >
              {isLoading ? (
                <Square className="h-4 w-4 fill-[#1F2023] animate-pulse" />
              ) : isRecording ? (
                <StopCircle className="h-5 w-5 text-red-500" />
              ) : hasContent ? (
                <ArrowUp className="h-4 w-4 text-[#1F2023]" />
              ) : (
                <Mic className="h-5 w-5 text-[#1F2023] transition-colors" />
              )}
            </Button>
          </PromptInputAction>
        </PromptInputActions>
      </PromptInput>

      <ImageViewDialog imageUrl={selectedImage} onClose={() => setSelectedImage(null)} />

      {/* Settings Modal */}
      <Dialog open={showSettings} onOpenChange={setShowSettings}>
        <DialogContent className="max-w-[400px] p-6 bg-[#1F2023]/95 backdrop-blur-xl border border-white/10 shadow-2xl rounded-2xl">
          <DialogTitle className="text-xl font-bold mb-4 text-white flex items-center gap-2">
            <Settings className="h-5 w-5 text-orange-400" />
            Model Settings
          </DialogTitle>
          
          <div className="space-y-4">
            {/* Free Tier Toggle */}
            <div className="flex items-center justify-between rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
              <div className="flex items-center gap-3">
                <div className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full",
                  freeTier ? "bg-emerald-500/20" : "bg-zinc-800"
                )}>
                  <svg className={cn("h-4 w-4", freeTier ? "text-emerald-400" : "text-zinc-500")} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-white">Free Tier</p>
                  <p className="text-[11px] text-zinc-400">Groq (llama-3.3-70b) — no API key needed</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setFreeTier(!freeTier)}
                className={cn(
                  "relative h-6 w-11 rounded-full transition-colors",
                  freeTier ? "bg-emerald-500" : "bg-zinc-700"
                )}
              >
                <span className={cn(
                  "absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform",
                  freeTier && "translate-x-5"
                )} />
              </button>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">LLM Provider</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full bg-[#09090b]/80 border border-white/10 rounded-lg p-2.5 text-white text-sm focus:outline-none focus:border-orange-500/50"
              >
                <option value="ollama">Ollama (Local - qwen2.5:1.5b)</option>
                <option value="groq">Groq (llama-3.3-70b) — Fastest</option>
                <option value="gemini">Google Gemini (gemini-2.5-flash)</option>
                <option value="openai">OpenAI (gpt-4o-mini)</option>
                <option value="anthropic">Anthropic (claude-3-haiku)</option>
                <option value="openrouter">OpenRouter (llama-3.1-8b)</option>
              </select>
            </div>

            {provider !== "ollama" && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-300">API Key</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={`Enter ${provider} API Key`}
                  className="w-full bg-[#09090b]/80 border border-white/10 rounded-lg p-2.5 text-white text-sm focus:outline-none focus:border-orange-500/50"
                />
              </div>
            )}

            <Button
              onClick={saveSettings}
              className="w-full mt-4 bg-zinc-950/60 backdrop-blur-md border border-orange-500/30 text-orange-400 font-medium rounded-2xl transition-all duration-200"
            >
              <span className="flex items-center justify-center gap-2">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 19v3" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><rect x="9" y="2" width="6" height="13" rx="3" />
                </svg>
                Save Settings
              </span>
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
});
PromptInputBox.displayName = "PromptInputBox";
