const SDK_VERSION = "12.4.0";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyD4yDALOVEL6fD8itCi_eNZ8V3itNDTjHE",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "rubber-gloves.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "rubber-gloves",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "rubber-gloves.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "975035281540",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:975035281540:web:065cfc90f955a576c712d1",
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || "G-THFPN4H7RW",
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL || "https://rubber-gloves-default-rtdb.firebaseio.com",
};

export const sortingLivePath = import.meta.env.VITE_FIREBASE_SORTING_PATH || "component3/status";

type Unsubscribe = () => void;
type FirebaseModule = Record<string, (...args: any[]) => any>;

async function loadModule(name: "app" | "analytics" | "database"): Promise<FirebaseModule> {
  const url = `https://www.gstatic.com/firebasejs/${SDK_VERSION}/firebase-${name}.js`;
  return import(/* @vite-ignore */ url) as Promise<FirebaseModule>;
}

export async function subscribeToSortingData(
  onData: (value: unknown) => void,
  onConnection: (connected: boolean) => void,
  onError: (error: Error) => void,
): Promise<Unsubscribe> {
  const [appSdk, analyticsSdk, databaseSdk] = await Promise.all([
    loadModule("app"), loadModule("analytics"), loadModule("database"),
  ]);
  const apps = appSdk.getApps() as unknown[];
  const app = apps[0] ?? appSdk.initializeApp(firebaseConfig);
  const analyticsSupported = await (analyticsSdk.isSupported() as Promise<boolean>);
  if (analyticsSupported) analyticsSdk.getAnalytics(app);

  const database = databaseSdk.getDatabase(app);
  const unsubscribeConnection = databaseSdk.onValue(
    databaseSdk.ref(database, ".info/connected"),
    (snapshot: { val: () => unknown }) => onConnection(snapshot.val() === true),
    (reason: Error) => onError(reason),
  ) as Unsubscribe;
  const unsubscribeSorting = databaseSdk.onValue(
    databaseSdk.ref(database, sortingLivePath),
    (snapshot: { exists: () => boolean; val: () => unknown }) => {
      onData(snapshot.exists() ? snapshot.val() : null);
    },
    (reason: Error) => onError(reason),
  ) as Unsubscribe;

  return () => {
    unsubscribeConnection();
    unsubscribeSorting();
  };
}
