"use client";

import React from "react";
import Link from "next/link";

export default function OfflinePage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="text-center max-w-md">
        <div className="w-20 h-20 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg className="w-10 h-10 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636a9 9 0 010 12.728m-2.829-2.829a5 5 0 000-7.07m-4.243 4.243a1 1 0 010-1.414" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">You&apos;re Offline</h1>
        <p className="text-gray-500 mb-6">
          AutoInsight AI needs an internet connection to process data and generate reports. 
          Please check your connection and try again.
        </p>
        <div className="space-y-3">
          <button
            onClick={() => window.location.reload()}
            className="btn-primary w-full"
          >
            Try Again
          </button>
          <Link href="/dashboard" className="btn-secondary w-full inline-flex items-center justify-center">
            Back to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
