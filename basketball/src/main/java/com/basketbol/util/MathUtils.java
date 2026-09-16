package com.basketbol.util;

public class MathUtils {
	public static double[] poissonDist(double lambda, int max) {
		double[] p = new double[max + 1];
		double e = Math.exp(-lambda);
		p[0] = e;
		for (int k = 1; k <= max; k++) {
			p[k] = p[k - 1] * lambda / k;
		}
		// normalize küçük hatalar için
		double sum = 0;
		for (double v : p)
			sum += v;
		if (Math.abs(sum - 1.0) > 1e-9) {
			for (int i = 0; i < p.length; i++)
				p[i] /= sum;
		}
		return p;
	}

	public static String fmtPct(double x) {
		return String.format("%.1f%%", x * 100.0);
	}
}
