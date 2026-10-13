import { apiClient } from "./api";
import { EvaluationMetricsResponse } from "../types/evaluation";

export const evaluationService = {
  async getEvaluationMetrics(): Promise<EvaluationMetricsResponse> {
    const response = await apiClient.get<EvaluationMetricsResponse>(
      "/evaluation/metrics"
    );
    return response.data;
  },
};
