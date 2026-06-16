import {
  doc,
  setDoc,
  getDoc,
  getDocs,
  deleteDoc,
  collection,
  query,
  orderBy,
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

export async function loadSession(user: User, sessionId: string) {
  const snap = await getDoc(sessionRef(user.uid, sessionId));
  if (!snap.exists()) return null;
  return { session_id: snap.id, ...snap.data() } as ChatSession;
}

export async function deleteSession(user: User, sessionId: string) {
  await deleteDoc(sessionRef(user.uid, sessionId));
}

export async function listSessions(user: User): Promise<ChatSession[]> {
  const q = query(userSessionsRef(user.uid), orderBy("timestamp", "desc"));
  const snap = await getDocs(q);
  return snap.docs.map((d) => ({ session_id: d.id, ...d.data() } as ChatSession));
}

export async function updateSessionItinerary(
  user: User,
  sessionId: string,
  itinerary: any,
  title?: string,
  destination?: string,
  userRequest?: string,
) {
  const ref = sessionRef(user.uid, sessionId);
  const now = Math.floor(Date.now() / 1000);
  const update: any = { itinerary, timestamp: now };
  if (title) update.title = title;
  if (destination) {
    update.destination = destination;
    update.destination_lower = destination.toLowerCase();
  }
  if (userRequest) update.user_request = userRequest;
  await setDoc(ref, update, { merge: true });
}
