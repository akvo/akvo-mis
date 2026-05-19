import React, { useMemo, useRef } from "react";
import "./style.scss";
import { store, uiText } from "../../lib";
import {
  HeroSection,
  MandateSection,
  VideoSection,
  RolesSection,
  HomeFooter,
  useHomeParallax,
  PhotoGallery,
} from "./components";

const Home = () => {
  const language = store.useState((s) => s.language);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const appName = window?.appConfig?.name || "IWSIMS";
  const rootRef = useRef(null);

  useHomeParallax(rootRef);

  return (
    <main className="home-content" ref={rootRef}>
      <HeroSection text={text} appName={appName} />
      <MandateSection text={text} />
      <VideoSection text={text} />
      <PhotoGallery text={text} />
      <RolesSection text={text} />
      <HomeFooter text={text} />
    </main>
  );
};

export default React.memo(Home);
