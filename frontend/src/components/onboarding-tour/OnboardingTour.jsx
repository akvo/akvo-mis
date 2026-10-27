import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Button, message } from "antd";
import {
  CloseOutlined,
  CopyOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
} from "@ant-design/icons";
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
    const CARD_WIDTH = 380;
    const CARD_HEIGHT = 260;

    setSpotlightRect({
      top: Math.max(0, rect.top - PADDING),
      left: Math.max(0, rect.left - PADDING),
      width: rect.width + PADDING * 2,
      height: rect.height + PADDING * 2,
    });

    let popLeft = rect.right + POPOVER_OFFSET;
    let popTop = rect.top;

    if (popLeft + CARD_WIDTH > window.innerWidth - 16) {
      popLeft = Math.max(16, rect.left - CARD_WIDTH - POPOVER_OFFSET);
    }
    if (popTop + CARD_HEIGHT > window.innerHeight - 16) {
      popTop = Math.max(16, window.innerHeight - CARD_HEIGHT - 16);
    }

    setPopoverCoords({
      top: popTop,
      left: popLeft,
    });
  }, [tourStep, currentStepConfig]);

  useEffect(() => {
    if (!tourOpen || tourStep <= 0) {
      setSpotlightRect(null);
      setPopoverCoords(null);
      return;
    }

    updateSpotlightPosition();

    const handleResizeOrScroll = () => {
      updateSpotlightPosition();
    };

    window.addEventListener("resize", handleResizeOrScroll);
    window.addEventListener("scroll", handleResizeOrScroll, true);

    return () => {
      window.removeEventListener("resize", handleResizeOrScroll);
      window.removeEventListener("scroll", handleResizeOrScroll, true);
    };
  }, [tourOpen, tourStep, updateSpotlightPosition]);

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
              <Button type="text" onClick={() => handleDismiss(true)}>
                {text.tourBtnSkip}
              </Button>
            </div>
            <div className="tour-footer-right">
              <Button
                type="primary"
                onClick={() => {
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
            className="onboarding-tour-spotlight-hole"
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

        {currentStepConfig.action === "copy_app_link" && (
          <div className="tour-step-action">
            <Button icon={<CopyOutlined />} onClick={handleCopyAppLink}>
              {text[currentStepConfig.actionLabelKey]}
            </Button>
          </div>
        )}

        <div className="tour-footer">
          <div className="tour-footer-left">
            <Button
              icon={<ArrowLeftOutlined />}
              onClick={() => {
                store.update((s) => {
                  s.tourStep = Math.max(0, tourStep - 1);
                });
              }}
            >
              {text.tourBtnBack}
            </Button>
          </div>

          <div className="tour-footer-right">
            {!isLastStep ? (
              <Button
                type="primary"
                onClick={() => {
                  store.update((s) => {
                    s.tourStep = tourStep + 1;
                  });
                }}
              >
                {text.tourBtnNext} <ArrowRightOutlined />
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
