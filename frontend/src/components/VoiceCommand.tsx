import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Mic,
  Square,
  AudioLines,
  Paperclip,
  FlaskConical,
  Volume2,
  VolumeX,
  LoaderCircle,
} from "lucide-react";
import { audioRequest } from "../api";
import { isApprovalCommand, type VoiceApproval } from "../voice";
export function VoiceCommand({
  busy,
  voiceAvailable,
  summary,
  onSubmit,
  onError,
  approvalContext,
  onVoiceApproval,
  onVoiceExecute,
}: {
  busy: boolean;
  voiceAvailable: boolean;
  summary?: string;
  onSubmit: (
    text: string,
    simulation: boolean,
    source?: string,
  ) => Promise<void>;
  onError: (error: string) => void;
  approvalContext?: VoiceApproval;
  onVoiceApproval: (context: VoiceApproval) => Promise<void>;
  onVoiceExecute: (context: VoiceApproval) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [simulation, setSimulation] = useState(false);
  const [state, setState] = useState("idle");
  const [speaking, setSpeaking] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [voiceApproval, setVoiceApproval] = useState<VoiceApproval | null>(
    null,
  );
  const [source, setSource] = useState("text");
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const objectUrl = useRef<string>("");
  const upload = useRef<HTMLInputElement>(null);
  const stopTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const disposed = useRef(false);
  useEffect(() => {
    disposed.current = false;
    return () => {
      disposed.current = true;
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach((t) => t.stop());
      audio.current?.pause();
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      if (stopTimer.current) clearTimeout(stopTimer.current);
    };
  }, []);
  useEffect(() => {
    if (state !== "listening") return;
    const timer = setInterval(() => setElapsed((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, [state]);
  async function submit() {
    if (!text.trim() || busy) return;
    await onSubmit(text, simulation, source);
    setText("");
    setSource("text");
  }
  function interrupt() {
    audio.current?.pause();
    setSpeaking(false);
  }
  async function startRecording() {
    interrupt();
    const confirmation = voiceApproval;
    const snapshot = approvalContext
      ? { ...approvalContext, captured_at: Date.now() }
      : undefined;
    try {
      if (!voiceAvailable)
        throw new Error(
          "Speech requires a server-side OpenAI key. Text input is ready to use.",
        );
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error("Microphone recording requires HTTPS or localhost.");
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = media;
      const chunks: BlobPart[] = [];
      const mime = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4";
      const rec = new MediaRecorder(media, { mimeType: mime });
      recorder.current = rec;
      rec.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data);
      };
      rec.onstop = () => {
        media.getTracks().forEach((t) => t.stop());
        if (stopTimer.current) clearTimeout(stopTimer.current);
        if (disposed.current) return;
        setState("transcribing");
        const form = new FormData();
        form.append(
          "audio",
          new Blob(chunks, { type: mime }),
          mime === "audio/webm" ? "recording.webm" : "recording.mp4",
        );
        void audioRequest("transcribe", form)
          .then((r) => r.json() as Promise<{ text: string }>)
          .then((result) => {
            setText(result.text);
            setSource("voice");
            if (isApprovalCommand(result.text)) {
              if (snapshot && snapshot.action_ids.length && !simulation)
                setVoiceApproval(snapshot);
              else
                onError(
                  "There is no current action plan to approve. Review a plan first.",
                );
            } else if (
              /^(yes|confirm approval)[.!]?$/i.test(result.text.trim()) &&
              confirmation
            ) {
              void onVoiceApproval(confirmation).then(() => {
                setVoiceApproval(null);
                setText("");
              });
            } else if (
              /^execute (the )?approved (plan|actions)[.!]?$/i.test(
                result.text.trim(),
              )
            ) {
              if (snapshot && !simulation)
                void onVoiceExecute(snapshot).then(() => setText(""));
              else
                onError(
                  "Review and approve a current plan before asking to execute it.",
                );
            }
            setState("idle");
          })
          .catch((e) => {
            onError(e instanceof Error ? e.message : "Transcription failed.");
            setState("idle");
          });
      };
      rec.start();
      setElapsed(0);
      setState("listening");
      stopTimer.current = setTimeout(() => {
        if (rec.state === "recording") rec.stop();
      }, 60000);
    } catch (e) {
      stream.current?.getTracks().forEach((t) => t.stop());
      onError(e instanceof Error ? e.message : "Microphone could not start.");
      setState("idle");
    }
  }
  async function speak() {
    if (speaking) {
      interrupt();
      return;
    }
    if (!summary) return;
    try {
      setState("synthesizing");
      const response = await audioRequest("speak", { text: summary });
      const blob = await response.blob();
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = URL.createObjectURL(blob);
      const player = new Audio(objectUrl.current);
      audio.current = player;
      player.onended = () => setSpeaking(false);
      await player.play();
      setSpeaking(true);
      setState("idle");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Speech playback failed.");
      setState("idle");
    }
  }
  async function readFile(file?: File) {
    if (!file) return;
    if (file.size > 50000) {
      onError("Please choose a text file smaller than 50 KB.");
      return;
    }
    setText(await file.text());
    setSource("upload");
  }
  return (
    <div className="command-area">
      {voiceApproval && (
        <div className="voice-approval" role="status">
          <div>
            <strong>Voice approval ready for review</strong>
            <p>
              “{text}” — {voiceApproval.action_ids.length} actions in plan
              version {voiceApproval.version}. Confirm against the previews
              above, or record “confirm approval”.
            </p>
          </div>
          <button
            className="button small"
            onClick={() => setVoiceApproval(null)}
          >
            Dismiss
          </button>
          <button
            className="button primary small"
            disabled={busy}
            onClick={() => {
              void onVoiceApproval(voiceApproval).then(() => {
                setVoiceApproval(null);
                setText("");
              });
            }}
          >
            Confirm voice approval
          </button>
        </div>
      )}
      <form
        className={`command-bar ${state === "listening" ? "listening" : ""}`}
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <AudioLines size={22} className="command-symbol" />
        <input
          aria-label="Tell LIFEOS what changed"
          placeholder={
            state === "listening"
              ? `Listening… ${elapsed}s`
              : "Tell LIFEOS what changed…"
          }
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setSource("text");
            setVoiceApproval(null);
          }}
          maxLength={12000}
          disabled={state === "listening" || state === "transcribing"}
        />
        <input
          ref={upload}
          type="file"
          accept="text/plain,.txt,.md"
          hidden
          onChange={(e) => void readFile(e.target.files?.[0])}
        />
        <button
          type="button"
          className="icon-button upload-button"
          aria-label="Upload text"
          title="Upload text"
          onClick={() => upload.current?.click()}
        >
          <Paperclip size={19} />
        </button>
        <button
          type="button"
          className={`icon-button ${simulation ? "selected" : ""}`}
          aria-label="What-if mode"
          aria-pressed={simulation}
          title="What-if mode"
          onClick={() => setSimulation(!simulation)}
        >
          <FlaskConical size={19} />
        </button>
        {summary && voiceAvailable && (
          <button
            type="button"
            className="icon-button"
            aria-label={speaking ? "Stop speaking" : "Read summary aloud"}
            title="AI-generated voice"
            onClick={() => void speak()}
          >
            {speaking ? <VolumeX size={19} /> : <Volume2 size={19} />}
          </button>
        )}
        <button
          type="button"
          className={`mic-button ${state === "listening" ? "recording" : ""}`}
          aria-label={
            state === "listening" ? "Stop recording" : "Start voice input"
          }
          title={
            voiceAvailable ? "Voice input" : "Configure OpenAI to enable voice"
          }
          onClick={() => {
            if (state === "listening") recorder.current?.stop();
            else void startRecording();
          }}
          disabled={state === "transcribing" || state === "synthesizing"}
        >
          {state === "listening" ? (
            <Square size={18} />
          ) : state === "transcribing" || state === "synthesizing" ? (
            <LoaderCircle size={18} className="spin" />
          ) : (
            <Mic size={19} />
          )}
        </button>
        <button
          type="submit"
          className="send-button"
          aria-label="Analyze change"
          disabled={busy || !text.trim()}
        >
          {busy ? (
            <LoaderCircle size={18} className="spin" />
          ) : (
            <ArrowUp size={19} />
          )}
        </button>
      </form>
      <div className="command-caption">
        <span>
          {simulation
            ? "What-if mode · Plans only, no changes"
            : state === "transcribing"
              ? "Transcribing your recording…"
              : state === "synthesizing"
                ? "Preparing AI-generated speech…"
                : "You stay in control. External actions require approval."}
        </span>
        <span>
          {voiceAvailable
            ? "Text + voice"
            : "Text ready · Voice needs configuration"}
        </span>
      </div>
    </div>
  );
}
