import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, type Auth } from "firebase/auth";
import { getFirestore, type Firestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

let _app: FirebaseApp | undefined;
let _auth: Auth | undefined;
let _db: Firestore | undefined;
let _provider: GoogleAuthProvider | undefined;

function init() {
  if (typeof window === "undefined") return;
  if (!_app) {
    _app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
    _auth = getAuth(_app);
    _db = getFirestore(_app);
    _provider = new GoogleAuthProvider();
  }
}

export function getFirebaseAuth(): Auth {
  init();
  if (!_auth) throw new Error("Firebase Auth not available server-side");
  return _auth;
}

export function getFirebaseDb(): Firestore {
  init();
  if (!_db) throw new Error("Firestore not available server-side");
  return _db;
}

export function getGoogleProvider(): GoogleAuthProvider {
  init();
  if (!_provider) throw new Error("Google provider not available server-side");
  return _provider;
}
