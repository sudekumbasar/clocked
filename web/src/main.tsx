import { render } from "preact";
import { lazy, Suspense } from "preact/compat";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { fetchItems, recognise, RecognitionError } from "./api";
import { discoveryView, type DiscoveryView } from "./discovery";
import { hasBeenWelcomed, markWelcomed } from "./home";
import { getLocation, getLocationIfAllowed } from "./location";
import { mapMarkers, nearestToFind } from "./map";
import { requestPersistentStorage, vibrate } from "./persist";
import { CameraScreen } from "./screens/Camera";
import { CategoryScreen } from "./screens/Category";
import { CollectionScreen } from "./screens/Collection";
import { DiscoveryScreen } from "./screens/Discovery";
import { HomeScreen } from "./screens/Home";
import { InstallBanner } from "./screens/InstallBanner";
import { ItemDetailScreen } from "./screens/ItemDetail";
import { WelcomeScreen } from "./screens/Welcome";
import { addDiscovery, listDiscoveries } from "./store";
import type { Discovery, Item, PlayerLocation } from "./types";
import "./styles.css";

// Test mode is a build-time switch: in the public build this is false and the
// import below is removed, so no test-mode code ships.
const TEST_MODE = import.meta.env.VITE_TEST_MODE === "1";
const TestTools = TEST_MODE ? lazy(() => import("./testmode/TestTools")) : null;
// The map (and its library) loads only when the player opens it.
const MapScreen = lazy(() => import("./screens/Map"));

type Screen =
  | { name: "welcome" }
  | { name: "home" }
  | { name: "camera" }
  | { name: "discovery"; view: DiscoveryView; photo: Blob }
  | { name: "collection" }
  | { name: "map" }
  | { name: "category"; category: string }
  | { name: "item"; itemId: string };

function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [discoveries, setDiscoveries] = useState<Discovery[]>([]);
  const [screen, setScreen] = useState<Screen>(() => (hasBeenWelcomed() ? { name: "home" } : { name: "welcome" }));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [showInstall, setShowInstall] = useState(false);
  const lastPhoto = useRef<Blob | null>(null);
  const [canRetry, setCanRetry] = useState(false);
  // Test mode only: "Pretend I am here". Always null in the public build.
  const [pretend, setPretend] = useState<{ id: string; location: PlayerLocation } | null>(null);
  // The last known position: from the latest photo, or read on the home screen when already allowed.
  const [known, setKnown] = useState<PlayerLocation | null>(null);
  const here = TEST_MODE && pretend ? pretend.location : known;

  async function refreshDiscoveries() {
    setDiscoveries(await listDiscoveries());
  }

  useEffect(() => {
    fetchItems().then(setItems).catch(() => setMessage("Couldn't load the collection list. Check your connection."));
    refreshDiscoveries();
  }, []);

  // On the home screen, refresh "nearest to find" without ever asking for permission there.
  useEffect(() => {
    if (screen.name !== "home") return;
    getLocationIfAllowed().then((location) => location && setKnown(location));
  }, [screen.name]);

  const nearest = useMemo(
    () => nearestToFind(mapMarkers(items, new Set(discoveries.map((d) => d.item_id)), here), here),
    [items, discoveries, here],
  );

  async function handlePhoto(photo: Blob) {
    lastPhoto.current = photo;
    setBusy(true);
    setMessage(null);
    setCanRetry(false);
    try {
      const location = TEST_MODE && pretend ? pretend.location : await getLocation();
      if (location && !(TEST_MODE && pretend)) setKnown(location);
      const result = await recognise(photo, location);
      const item = result.outcome === "AWARD" ? items.find((i) => i.id === result.item_id) : undefined;
      if (!item) {
        setMessage(result.message);
        return;
      }
      const { isNew, discovery, photo: added } = await addDiscovery(item.id, photo);
      const all = await listDiscoveries();
      setDiscoveries(all);
      const ids = new Set(all.map((d) => d.item_id));
      setScreen({
        name: "discovery",
        view: discoveryView(item, items, ids, isNew, discovery.first_found_at),
        // A new item shows its stamp; an item found again shows the photo just taken,
        // which is now kept with the item's other photos.
        photo: isNew ? discovery.photo : added.photo,
      });
      if (isNew) {
        vibrate();
        requestPersistentStorage();
        setShowInstall(true);
      }
    } catch (error) {
      // The photo is kept so it can be retried (PRODUCT.md, "When things go wrong").
      setMessage(error instanceof RecognitionError ? error.message : String(error));
      setCanRetry(true);
    } finally {
      setBusy(false);
    }
  }

  const latest = discoveries[0]?.photo ?? null; // listDiscoveries gives the newest first

  return (
    <>
      {screen.name === "welcome" && (
        <WelcomeScreen
          onStart={() => {
            markWelcomed();
            setScreen({ name: "home" });
          }}
        />
      )}
      {screen.name === "home" && (
        <HomeScreen
          items={items}
          discoveries={discoveries}
          nearest={nearest}
          here={here}
          message={busy ? null : message}
          onTakePhoto={() => {
            setMessage(null);
            setScreen({ name: "camera" });
          }}
          onOpenCollection={() => setScreen({ name: "collection" })}
          onOpenMap={() => setScreen({ name: "map" })}
        />
      )}
      {screen.name === "camera" && (
        <CameraScreen
          busy={busy}
          message={message}
          canRetry={canRetry}
          latestPhoto={latest}
          onPhoto={handlePhoto}
          onRetry={() => lastPhoto.current && handlePhoto(lastPhoto.current)}
          onOpenCollection={() => setScreen({ name: "collection" })}
          onOpenMap={() => setScreen({ name: "map" })}
          onHome={() => setScreen({ name: "home" })}
          testTools={
            TestTools && (
              <Suspense fallback={null}>
                <TestTools
                  busy={busy}
                  items={items}
                  pretendId={pretend?.id ?? null}
                  onPhoto={handlePhoto}
                  onReset={refreshDiscoveries}
                  onPretend={(id, location) => setPretend(id && location ? { id, location } : null)}
                />
              </Suspense>
            )
          }
        />
      )}
      {screen.name === "discovery" && (
        <DiscoveryScreen view={screen.view} photo={screen.photo} onContinue={() => setScreen({ name: "camera" })} />
      )}
      {screen.name === "collection" && (
        <CollectionScreen
          items={items}
          discoveries={discoveries}
          onBack={() => setScreen({ name: "home" })}
          onOpenCategory={(category) => setScreen({ name: "category", category })}
        />
      )}
      {screen.name === "map" && (
        <Suspense fallback={<div class="looking">Loading map…</div>}>
          <MapScreen
            items={items}
            discoveries={discoveries}
            pretend={TEST_MODE ? (pretend?.location ?? null) : null}
            onBack={() => setScreen({ name: "home" })}
          />
        </Suspense>
      )}
      {screen.name === "category" && (
        <CategoryScreen
          category={screen.category}
          items={items}
          discoveries={discoveries}
          onBack={() => setScreen({ name: "collection" })}
          onOpenItem={(itemId) => setScreen({ name: "item", itemId })}
        />
      )}
      {screen.name === "item" && (() => {
        const item = items.find((i) => i.id === screen.itemId);
        const discovery = discoveries.find((d) => d.item_id === screen.itemId);
        return item && discovery ? (
          <ItemDetailScreen
            item={item}
            items={items}
            discovery={discovery}
            onChanged={refreshDiscoveries}
            onBack={() => setScreen({ name: "category", category: item.category })}
          />
        ) : null;
      })()}
      {showInstall && screen.name === "camera" && <InstallBanner />}
    </>
  );
}

render(<App />, document.getElementById("app")!);
