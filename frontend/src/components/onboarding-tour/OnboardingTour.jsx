import React, {
  useState,
  useEffect,
  useMemo,
  useCallback,
  useRef,
} from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button, message } from "antd";
import { CloseOutlined } from "@ant-design/icons";
import { store } from "../../lib";
import uiText from "../../lib/ui-text";
import {
  GOAL_DEFINITIONS,
  TOUR_PATHS,
  getAvailableGoals,
  getRecommendedGoal,
  getTotalStepsForGoal,
} from "./tourConfig";
import "./style.scss";

/**
 * Returns the localStorage key for tracking tour completion.
 * @param {object|null} user
 * @param {object|null} tenant
 * @returns {string}
 */
export const getStorageKey = (user, tenant) => {
  const tenantSubdomain = tenant?.subdomain || "default";
  const userId = user?.id || "guest";
  return `akvo_mis_tour_completed_${userId}_${tenantSubdomain}`;
};

const OnboardingTour = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    tourOpen,
    tourGoal,
    tourStep,
    user: authUser,
    tenant,
    language,
  } = store.useState((s) => s);

  const activeLang = language?.active || "en";
  const text = useMemo(() => uiText[activeLang] || uiText.en, [activeLang]);

  const availableGoals = useMemo(() => getAvailableGoals(authUser), [authUser]);
  const recommendedGoal = useMemo(
    () => getRecommendedGoal(authUser),
    [authUser]
  );

  const [selectedGoal, setSelectedGoal] = useState(() => {
    return tourGoal || recommendedGoal;
  });

  const cardRef = useRef(null);
  const [spotlightRect, setSpotlightRect] = useState(null);
  const [popoverCoords, setPopoverCoords] = useState(null);

  // Sync selectedGoal when tourGoal in store or recommendedGoal changes
  useEffect(() => {
    if (tourGoal) {
      setSelectedGoal(tourGoal);
    } else if (availableGoals.includes(recommendedGoal)) {
      setSelectedGoal(recommendedGoal);
    } else if (availableGoals.length > 0) {
      setSelectedGoal(availableGoals[0]);
    }
  }, [tourGoal, recommendedGoal, availableGoals]);

  const currentGoal = selectedGoal || recommendedGoal;
  const totalSteps = useMemo(
    () => getTotalStepsForGoal(currentGoal),
    [currentGoal]
  );
  const currentPath = useMemo(
    () => TOUR_PATHS[currentGoal] || [],
    [currentGoal]
  );
  const currentStepConfig = useMemo(() => {
    if (tourStep <= 0 || !currentPath) {
      return null;
    }
    return currentPath[tourStep - 1] || null;
  }, [tourStep, currentPath]);

  // Dismiss tour and optionally mark completed in localStorage
  const handleDismiss = useCallback(
    (markCompleted = true) => {
      if (markCompleted && authUser?.id) {
        try {
          localStorage.setItem(getStorageKey(authUser, tenant), "true");
        } catch (err) {
          // Ignore localStorage access failures
        }
      }
      store.update((s) => {
        s.tourOpen = false;
        s.tourStep = 0;
      });
    },
    [authUser, tenant]
  );

  // Measure target DOM element for steps 2+
  const updateSpotlightPosition = useCallback(() => {
    if (tourStep <= 0 || !currentStepConfig) {
      setSpotlightRect(null);
      setPopoverCoords(null);
      return;
    }

    let targetEl = null;
    if (currentStepConfig.targetSelector) {
      targetEl = document.querySelector(currentStepConfig.targetSelector);
    }
    if (!targetEl && currentStepConfig.fallbackSelector) {
      targetEl = document.querySelector(currentStepConfig.fallbackSelector);
    }

    if (!targetEl) {
      setSpotlightRect(null);
      setPopoverCoords(null);
      return;
    }

    const rect = targetEl.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      setSpotlightRect(null);
      setPopoverCoords(null);
      return;
    }

    const PADDING = 6;
    const POPOVER_OFFSET = 12;
    const cardEl = cardRef.current;
    const cardWidth = cardEl?.offsetWidth || 390;
    const cardHeight = cardEl?.offsetHeight || 250;

    const isCircular =
      currentStepConfig.targetSelector === ".chatbot-fab-btn" ||
      (Math.abs(rect.width - rect.height) < 10 && rect.width < 70);

    setSpotlightRect({
      top: Math.max(0, rect.top - PADDING),
      left: Math.max(0, rect.left - PADDING),
      width: rect.width + PADDING * 2,
      height: rect.height + PADDING * 2,
      isCircular,
    });

    const targetCenterX = rect.left + rect.width / 2;
    const targetCenterY = rect.top + rect.height / 2;

    let arrow = "left";
    let popLeft = rect.right + POPOVER_OFFSET;
    // Vertically center the popover on the target element by default
    let popTop = targetCenterY - cardHeight / 2;

    // 1. If target is in bottom-right corner (Chatbot FAB button)
    if (
      rect.right > window.innerWidth - 120 &&
      rect.bottom > window.innerHeight - 120
    ) {
      popLeft = Math.max(16, rect.right - cardWidth + 8);
      popTop = Math.max(16, rect.top - cardHeight - POPOVER_OFFSET);
      arrow = "bottom";
    } else if (rect.left > 180) {
      // 2. If target is a main content panel (e.g. Submissions or Approvals)
      popLeft = Math.max(16, rect.left + 16);
      popTop = rect.bottom + POPOVER_OFFSET;
      arrow = "top";
    }

    if (popLeft + cardWidth > window.innerWidth - 16) {
      popLeft = Math.max(16, window.innerWidth - cardWidth - 16);
    }
    if (popTop + cardHeight > window.innerHeight - 16) {
      popTop = Math.max(16, window.innerHeight - cardHeight - 16);
    }
    popTop = Math.max(16, popTop);

    // Compute dynamic arrow offset along the card edge to point directly at target center
    let arrowOffset = 36;
    if (arrow === "left") {
      arrowOffset = targetCenterY - popTop;
      arrowOffset = Math.max(18, Math.min(cardHeight - 18, arrowOffset));
    } else if (arrow === "top" || arrow === "bottom") {
      arrowOffset = targetCenterX - popLeft;
      arrowOffset = Math.max(18, Math.min(cardWidth - 18, arrowOffset));
    }

    setPopoverCoords({
      top: popTop,
      left: popLeft,
      arrow,
      arrowOffset,
    });
  }, [tourStep, currentStepConfig]);

  useEffect(() => {
    if (!tourOpen || tourStep <= 0) {
      setSpotlightRect(null);
      setPopoverCoords(null);
      return;
    }

    const scrollToTarget = () => {
      let targetEl = null;
      if (currentStepConfig?.targetSelector) {
        targetEl = document.querySelector(currentStepConfig.targetSelector);
      }
      if (!targetEl && currentStepConfig?.fallbackSelector) {
        targetEl = document.querySelector(currentStepConfig.fallbackSelector);
      }

      if (!targetEl) {
        return;
      }

      const isPanel =
        currentStepConfig?.targetSelector === "#panel-submission" ||
        currentStepConfig?.targetSelector === "#panel-approvals";

      const rect = targetEl.getBoundingClientRect();
      const viewportHeight =
        window.innerHeight || document.documentElement.clientHeight || 800;
      const isOffscreen = rect.top < 90 || rect.bottom > viewportHeight - 40;

      if (isPanel || isOffscreen) {
        // Native element.scrollIntoView works across any scrolling container (window, #root, .ant-layout)
        if (typeof targetEl.scrollIntoView === "function") {
          try {
            targetEl.scrollIntoView({ behavior: "smooth", block: "center" });
          } catch (e) {
            targetEl.scrollIntoView(true);
          }
        }

        // Also scroll window / root container directly as fallback taking fixed header into account
        const headerOffset = 100;
        const currentScroll =
          window.pageYOffset ||
          document.documentElement.scrollTop ||
          document.body.scrollTop ||
          0;
        const targetScrollTop = Math.max(
          0,
          rect.top + currentScroll - headerOffset
        );

        if (typeof window.scrollTo === "function") {
          try {
            window.scrollTo({
              top: targetScrollTop,
              behavior: "smooth",
            });
          } catch (e) {
            window.scrollTo(0, targetScrollTop);
          }
        }
        const rootEl = document.getElementById("root");
        if (rootEl && typeof rootEl.scrollTo === "function") {
          try {
            rootEl.scrollTo({
              top: targetScrollTop,
              behavior: "smooth",
            });
          } catch (e) {
            rootEl.scrollTop = targetScrollTop;
          }
        }
      } else {
        // If moving back to a step on the fixed sidebar or chatbot and page was scrolled down,
        // smoothly scroll back to top so the full context is visible
        const rootEl = document.getElementById("root");
        const currentScroll =
          window.pageYOffset ||
          document.documentElement.scrollTop ||
          document.body.scrollTop ||
          rootEl?.scrollTop ||
          0;

        if (currentScroll > 50) {
          if (typeof window.scrollTo === "function") {
            try {
              window.scrollTo({ top: 0, behavior: "smooth" });
            } catch (e) {
              window.scrollTo(0, 0);
            }
          }
          if (rootEl && typeof rootEl.scrollTo === "function") {
            try {
              rootEl.scrollTo({ top: 0, behavior: "smooth" });
            } catch (e) {
              rootEl.scrollTop = 0;
            }
          }
        }
      }
    };

    scrollToTarget();
    const immediateScrollTimer = setTimeout(scrollToTarget, 50);

    updateSpotlightPosition();

    // Re-check spotlight position after smooth scroll animation completes
    const settleTimer1 = setTimeout(() => {
      updateSpotlightPosition();
    }, 200);

    const settleTimer2 = setTimeout(() => {
      updateSpotlightPosition();
    }, 500);

    const handleResizeOrScroll = () => {
      updateSpotlightPosition();
    };

    window.addEventListener("resize", handleResizeOrScroll);
    window.addEventListener("scroll", handleResizeOrScroll, true);

    return () => {
      clearTimeout(immediateScrollTimer);
      clearTimeout(settleTimer1);
      clearTimeout(settleTimer2);
      window.removeEventListener("resize", handleResizeOrScroll);
      window.removeEventListener("scroll", handleResizeOrScroll, true);
    };
  }, [
    tourOpen,
    tourStep,
    currentStepConfig,
    updateSpotlightPosition,
    location.pathname,
  ]);

  // Fallback copy for environments without navigator.clipboard
  const fallbackCopy = (textToCopy) => {
    try {
      const textArea = document.createElement("textarea");
      textArea.value = textToCopy;
      textArea.style.position = "fixed";
      textArea.style.left = "-999999px";
      textArea.style.top = "-999999px";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      const successful = document.execCommand("copy");
      document.body.removeChild(textArea);
      if (successful) {
        message.success(
          text.tourLinkCopied || "App download link copied to clipboard"
        );
      } else {
        message.error(
          text.tourLinkCopyError || "Unable to copy link to clipboard"
        );
      }
    } catch (err) {
      message.error(
        text.tourLinkCopyError || "Unable to copy link to clipboard"
      );
    }
  };

  const handleCopyAppLink = () => {
    const appUrl = `${window.location.origin}/app`;
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard
        .writeText(appUrl)
        .then(() => {
          message.success(
            text.tourLinkCopied || "App download link copied to clipboard"
          );
        })
        .catch(() => {
          fallbackCopy(appUrl);
        });
    } else {
      fallbackCopy(appUrl);
    }
  };

  if (!tourOpen) {
    return null;
  }

  // STEP 1: Welcome & Goal Picker Modal View
  if (tourStep === 0) {
    const isSingleGoal = availableGoals.length === 1;
    const stepLabel = (text.tourStepOf || "STEP {current} OF {total}")
      .replace("{current}", 1)
      .replace("{total}", totalSteps);

    return (
      <div
        className="onboarding-tour-backdrop centered"
        role="dialog"
        aria-modal="true"
      >
        <div className="onboarding-tour-card modal-view">
          <span
            className="tour-close-btn"
            onClick={() => handleDismiss(true)}
            role="button"
            aria-label="Close"
          >
            <CloseOutlined />
          </span>

          <div className="tour-step-indicator">{stepLabel}</div>
          <h2 className="tour-title">{text.tourWelcomeTitle}</h2>
          <p className="tour-subtitle">{text.tourWelcomeSubtitle}</p>

          <div className="tour-goals-container">
            {availableGoals.map((goalKey) => {
              const def = GOAL_DEFINITIONS[goalKey];
              if (!def) {
                return null;
              }
              const isSelected = currentGoal === goalKey;
              const isRecommended = goalKey === recommendedGoal;

              return (
                <div
                  key={goalKey}
                  className={`tour-goal-card ${isSelected ? "selected" : ""} ${
                    isSingleGoal ? "single-mode" : ""
                  }`}
                  onClick={() => {
                    if (!isSingleGoal) {
                      setSelectedGoal(goalKey);
                      store.update((s) => {
                        s.tourGoal = goalKey;
                      });
                    }
                  }}
                  role={isSingleGoal ? "region" : "radio"}
                  {...(isSingleGoal ? {} : { "aria-checked": isSelected })}
                >
                  {!isSingleGoal && (
                    <div
                      className={`tour-radio-indicator ${
                        isSelected ? "checked" : ""
                      }`}
                    />
                  )}
                  <div className="tour-goal-content">
                    <div className="tour-goal-header">
                      <span className="tour-goal-title">
                        {text[def.titleKey]}
                      </span>
                      {isRecommended && !isSingleGoal && (
                        <span className="tour-badge-recommended">
                          {text.tourGoalRecommended}
                        </span>
                      )}
                    </div>
                    <div className="tour-goal-desc">{text[def.descKey]}</div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="tour-footer">
            <div className="tour-footer-left">
              <div className="tour-dots">
                {Array.from({ length: totalSteps }).map((_, idx) => (
                  <span
                    key={idx}
                    className={`tour-dot ${idx === 0 ? "active" : ""}`}
                  />
                ))}
              </div>
            </div>
            <div className="tour-footer-right">
              <Button onClick={() => handleDismiss(true)}>
                {text.tourBtnSkip}
              </Button>
              <Button
                type="primary"
                onClick={() => {
                  if (location.pathname !== "/control-center") {
                    navigate("/control-center");
                  }
                  store.update((s) => {
                    s.tourGoal = currentGoal;
                    s.tourStep = 1;
                  });
                }}
              >
                {text.tourBtnShowMeHow}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // STEPS 2+: Spotlight Cutout & Popover Card View
  if (!currentStepConfig) {
    return null;
  }

  const isLastStep = tourStep === currentPath.length;
  const currentStepNumber = tourStep + 1;
  const stepLabel = (text.tourStepOf || "STEP {current} OF {total}")
    .replace("{current}", currentStepNumber)
    .replace("{total}", totalSteps);

  const hasSpotlight = Boolean(spotlightRect);

  return (
    <>
      {hasSpotlight ? (
        <>
          <div
            className={`onboarding-tour-spotlight-hole ${
              spotlightRect.isCircular ? "circle-spotlight" : ""
            }`}
            style={{
              top: `${spotlightRect.top}px`,
              left: `${spotlightRect.left}px`,
              width: `${spotlightRect.width}px`,
              height: `${spotlightRect.height}px`,
            }}
          />
          <div
            className="onboarding-tour-backdrop"
            onClick={() => handleDismiss(true)}
          />
        </>
      ) : (
        <div className="onboarding-tour-backdrop centered" />
      )}

      <div
        ref={cardRef}
        className={`onboarding-tour-card popover-view ${
          hasSpotlight ? "" : "fallback-center"
        }`}
        style={
          hasSpotlight && popoverCoords
            ? {
                top: `${popoverCoords.top}px`,
                left: `${popoverCoords.left}px`,
              }
            : null
        }
        role="dialog"
        aria-modal="true"
      >
        {hasSpotlight && popoverCoords?.arrow && (
          <div
            className={`tour-card-arrow arrow-${popoverCoords.arrow}`}
            style={
              popoverCoords.arrow === "left"
                ? { top: `${popoverCoords.arrowOffset}px` }
                : { left: `${popoverCoords.arrowOffset}px` }
            }
          />
        )}

        <span
          className="tour-close-btn"
          onClick={() => handleDismiss(true)}
          role="button"
          aria-label="Close"
        >
          <CloseOutlined />
        </span>

        <div className="tour-step-indicator">{stepLabel}</div>
        <h3 className="tour-title">{text[currentStepConfig.titleKey]}</h3>
        <p className="tour-body-text">{text[currentStepConfig.descKey]}</p>

        {currentStepConfig.illustration === "form" && (
          <div className="tour-wireframe-card">
            <div className="wireframe-header-bar" />
            <div className="wireframe-sub-bar" />
            <div className="wireframe-form-row">
              <div className="wireframe-radio-circle" />
              <div className="wireframe-input-bar" />
              <div className="wireframe-button-pill" />
            </div>
          </div>
        )}

        {currentStepConfig.action === "copy_app_link" && (
          <div className="tour-step-action">
            <button
              className="tour-dashed-copy-btn"
              onClick={handleCopyAppLink}
              type="button"
            >
              {text[currentStepConfig.actionLabelKey]}
            </button>
          </div>
        )}

        <div className="tour-footer">
          <div className="tour-footer-left">
            <div className="tour-dots">
              {Array.from({ length: totalSteps }).map((_, idx) => (
                <span
                  key={idx}
                  className={`tour-dot ${idx === tourStep ? "active" : ""}`}
                />
              ))}
            </div>
            <span
              className="tour-skip-tour-link"
              onClick={() => handleDismiss(true)}
              role="button"
            >
              {text.tourBtnSkip || "Skip tour"}
            </span>
          </div>

          <div className="tour-footer-right">
            <Button
              onClick={() => {
                store.update((s) => {
                  s.tourStep = Math.max(0, tourStep - 1);
                });
              }}
            >
              {text.tourBtnBack}
            </Button>

            {!isLastStep ? (
              <Button
                type="primary"
                onClick={() => {
                  store.update((s) => {
                    s.tourStep = tourStep + 1;
                  });
                }}
              >
                {text.tourBtnNext}
              </Button>
            ) : (
              <Button
                type="primary"
                onClick={() => {
                  handleDismiss(true);
                  if (currentStepConfig.ctaRoute) {
                    const navOptions = currentStepConfig.ctaState
                      ? { state: currentStepConfig.ctaState }
                      : {};
                    navigate(currentStepConfig.ctaRoute, navOptions);
                  }
                }}
              >
                {text[currentStepConfig.ctaLabelKey]}
              </Button>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default OnboardingTour;
