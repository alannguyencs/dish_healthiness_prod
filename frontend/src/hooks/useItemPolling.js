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
 *   - pollingStep1, pollingStep2 (which spinner to show, if any)
 *   - confirmedStep1Data (parsed for the editor's re-entry path)
 *   - reload(): force a fresh fetch + re-evaluation
 *   - startPollingStep1() / startPollingStep2(): re-arm after a user retry/confirm
 */
const useItemPolling = (recordId) => {
  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pollingStep1, setPollingStep1] = useState(false);
  const [pollingStep2, setPollingStep2] = useState(false);
  const [confirmedStep1Data, setConfirmedStep1Data] = useState(null);
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
        setPollingStep1(true);
        return;
      }
      if (
        resultGemini.confirmed_components &&
        resultGemini.confirmed_dish_name
      ) {
        setConfirmedStep1Data({
          selected_dish_name: resultGemini.confirmed_dish_name,
          components: resultGemini.confirmed_components,
        });
      }

      if (!resultGemini.step1_data && !resultGemini.step1_error) {
        setPollingStep1(true);
      } else if (resultGemini.step1_error && !resultGemini.step1_data) {
        setPollingStep1(false);
        setPollingStep2(false);
        stopPolling();
      } else if (resultGemini.step === 1 && !resultGemini.step1_confirmed) {
        setPollingStep1(false);
        setPollingStep2(false);
        stopPolling();
      } else if (
        resultGemini.step1_confirmed &&
        !resultGemini.step2_data &&
        !resultGemini.step2_error
      ) {
        setPollingStep1(false);
        setPollingStep2(true);
      } else {
        setPollingStep1(false);
        setPollingStep2(false);
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
          (rg.step === 1 && !rg.step1_confirmed) ||
          rg.step1_error ||
          rg.step2_data ||
          rg.step2_error
        ) {
          setPollingStep1(false);
          setPollingStep2(false);
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
      setPollingStep1(false);
      setPollingStep2(false);
      stopPolling();
    } finally {
      setLoading(false);
    }
  }, [recordId, evaluateState, stopPolling]);

  // Whenever a polling flag flips on, ensure the interval is running.
  useEffect(() => {
    if (pollingStep1 || pollingStep2) startPolling();
  }, [pollingStep1, pollingStep2, startPolling]);

  useEffect(() => {
    reload();
    return stopPolling;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordId]);

  const startPollingStep1 = () => setPollingStep1(true);
  const startPollingStep2 = () => setPollingStep2(true);

  return {
    item,
    loading,
    error,
    pollingStep1,
    pollingStep2,
    confirmedStep1Data,
    setConfirmedStep1Data,
    reload,
    startPollingStep1,
    startPollingStep2,
  };
};

export default useItemPolling;
