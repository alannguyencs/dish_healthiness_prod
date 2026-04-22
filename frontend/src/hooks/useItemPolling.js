import { useCallback, useEffect, useRef, useState } from "react";
import apiService from "../services/api";

/**
 * useItemPolling
 *
 * Owns the GET /api/item/{id} fetch + 3-second polling lifecycle for the
 * Phase 1 / Phase 2 dish analysis page. Stops polling whenever the record's
 * `result_gemini` reaches a terminal state for the current phase: success
 * data present OR error block present.
 *
 * Returns:
 *   - item, loading, error (initial fetch state)
 *   - pollingIdentification, pollingNutrition (which spinner to show, if any)
 *   - confirmedIdentificationData (parsed for the editor's re-entry path)
 *   - reload(): force a fresh fetch + re-evaluation
 *   - startPollingIdentification() / startPollingNutrition(): re-arm after a
 *     user retry/confirm
 */
const useItemPolling = (recordId) => {
  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pollingIdentification, setPollingIdentification] = useState(false);
  const [pollingNutrition, setPollingNutrition] = useState(false);
  const [confirmedIdentificationData, setConfirmedIdentificationData] =
    useState(null);
  const intervalRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const evaluateState = useCallback(
    (resultGemini) => {
      if (!resultGemini) {
        setPollingIdentification(true);
        return;
      }
      if (
        resultGemini.confirmed_components &&
        resultGemini.confirmed_dish_name
      ) {
        setConfirmedIdentificationData({
          selected_dish_name: resultGemini.confirmed_dish_name,
          components: resultGemini.confirmed_components,
        });
      }

      if (
        !resultGemini.identification_data &&
        !resultGemini.identification_error
      ) {
        setPollingIdentification(true);
      } else if (
        resultGemini.identification_error &&
        !resultGemini.identification_data
      ) {
        setPollingIdentification(false);
        setPollingNutrition(false);
        stopPolling();
      } else if (
        resultGemini.phase === 1 &&
        !resultGemini.identification_confirmed
      ) {
        setPollingIdentification(false);
        setPollingNutrition(false);
        stopPolling();
      } else if (
        resultGemini.identification_confirmed &&
        !resultGemini.nutrition_data &&
        !resultGemini.nutrition_error
      ) {
        setPollingIdentification(false);
        setPollingNutrition(true);
      } else {
        setPollingIdentification(false);
        setPollingNutrition(false);
        stopPolling();
      }
    },
    [stopPolling],
  );

  const startPolling = useCallback(() => {
    if (intervalRef.current) return;
    intervalRef.current = setInterval(async () => {
      try {
        const data = await apiService.getItem(recordId);
        setItem(data);
        const rg = data.result_gemini;
        if (!rg) return;
        if (
          (rg.phase === 1 && !rg.identification_confirmed) ||
          rg.identification_error ||
          rg.nutrition_data ||
          rg.nutrition_error
        ) {
          setPollingIdentification(false);
          setPollingNutrition(false);
          stopPolling();
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 3000);
  }, [recordId, stopPolling]);

  const reload = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiService.getItem(recordId);
      setItem(data);
      setError(null);
      evaluateState(data.result_gemini);
    } catch (err) {
      console.error(err);
      setError("Failed to load item details");
      setPollingIdentification(false);
      setPollingNutrition(false);
      stopPolling();
    } finally {
      setLoading(false);
    }
  }, [recordId, evaluateState, stopPolling]);

  // Whenever a polling flag flips on, ensure the interval is running.
  useEffect(() => {
    if (pollingIdentification || pollingNutrition) startPolling();
  }, [pollingIdentification, pollingNutrition, startPolling]);

  useEffect(() => {
    reload();
    return stopPolling;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordId]);

  const startPollingIdentification = () => setPollingIdentification(true);
  const startPollingNutrition = () => setPollingNutrition(true);

  return {
    item,
    loading,
    error,
    pollingIdentification,
    pollingNutrition,
    confirmedIdentificationData,
    setConfirmedIdentificationData,
    reload,
    startPollingIdentification,
    startPollingNutrition,
  };
};

export default useItemPolling;
