import {
  doc,
  setDoc,
  getDoc,
  getDocs,
  deleteDoc,
  collection,
  query,
  orderBy,
  serverTimestamp,
} from "firebase/firestore";
import { getFirebaseDb } from "./firebase";
import type { User } from "firebase/auth";

export interface ChatSession {
  session_id: string;
  title: string;
  destination: string;
  timestamp: number;
  itinerary?: any;
  messages?: any[];
}

function getDb() {
  return getFirebaseDb();
}

function userSessionsRef(uid: string) {
  return collection(getDb(), "users", uid, "sessions");
}

function sessionRef(uid: string, sessionId: string) {
  return doc(getDb(), "users", uid, "sessions", sessionId);
}

export async function saveSession(
  user: User,
  sessionId: string,
  data: Partial<ChatSession>
) {
  const ref = sessionRef(user.uid, sessionId);
  await setDoc(
    ref,
    {
      ...data,
      userId: user.uid,
      createdAt: serverTimestamp(),
    },
    { merge: true }
  );
}

export async function loadSession(user: User, sessionId: string) {
  const snap = await getDoc(sessionRef(user.uid, sessionId));
  if (!snap.exists()) return null;
  return { session_id: snap.id, ...snap.data() } as ChatSession;
}

export async function deleteSession(user: User, sessionId: string) {
  await deleteDoc(sessionRef(user.uid, sessionId));
}

export async function listSessions(user: User): Promise<ChatSession[]> {
  const q = query(userSessionsRef(user.uid), orderBy("createdAt", "desc"));
  const snap = await getDocs(q);
  return snap.docs.map((d) => ({ session_id: d.id, ...d.data() } as ChatSession));
}

export async function updateSessionItinerary(
  user: User,
  sessionId: string,
  itinerary: any,
  title?: string,
  destination?: string
) {
  const ref = sessionRef(user.uid, sessionId);
  const update: any = { itinerary, timestamp: Date.now() };
  if (title) update.title = title;
  if (destination) update.destination = destination;
  await setDoc(ref, update, { merge: true });
}
