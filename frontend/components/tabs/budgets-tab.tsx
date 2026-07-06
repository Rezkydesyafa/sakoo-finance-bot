export function BudgetsTab() {
  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="hidden md:block max-w-container-max mx-auto">
        {/* Header Section */}
        <div className="flex justify-between items-end mb-8">
          <div>
            <h2 className="font-headline-hero text-headline-hero text-text-primary mb-2 dark:text-white">Manage Your Budgets</h2>
            <p className="font-body-main text-body-main text-text-muted">Stay on track with your monthly spending limits.</p>
          </div>
          <button className="bg-primary-container text-on-primary-container font-label-button text-label-button px-6 py-3 rounded-full hover:opacity-90 transition-all active:scale-95 flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px]">add</span>
            Set New Budget
          </button>
        </div>
        
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          <div className="bg-white rounded-[24px] p-6 card-shadow flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#5f5e5e]">
                <span className="material-symbols-outlined text-[20px]">account_balance_wallet</span>
              </div>
              <span className="text-sm font-semibold text-[#6F6F6F]">Total Budgeted</span>
            </div>
            <div className="text-2xl font-bold text-[#1a1c1b]">Rp5.000.000</div>
          </div>
          
          <div className="bg-[#2A2A2A] rounded-[24px] p-6 card-shadow flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-[#c7ff00] opacity-10 rounded-full blur-2xl transform translate-x-1/2 -translate-y-1/2"></div>
            <div className="flex items-center justify-between mb-4 relative z-10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[#1a1c1b] flex items-center justify-center text-white">
                  <span className="material-symbols-outlined text-[20px]">savings</span>
                </div>
                <span className="text-sm font-semibold text-white opacity-80">Remaining</span>
              </div>
              <div className="bg-[#c7ff00] text-[#151f00] text-[11px] font-bold px-3 py-1 rounded-full">Healthy</div>
            </div>
            <div className="text-2xl font-bold text-white relative z-10">Rp1.250.000</div>
          </div>
          
          <div className="bg-white rounded-[24px] p-6 card-shadow flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#5f5e5e]">
                <span className="material-symbols-outlined text-[20px]">flag</span>
              </div>
              <span className="text-sm font-semibold text-[#6F6F6F]">Savings Goal</span>
            </div>
            <div className="text-2xl font-bold text-[#1a1c1b]">Rp2.000.000</div>
          </div>
        </div>
        
        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-gutter">
          {/* Budget List (Col 1-2) */}
          <div className="lg:col-span-2 space-y-stack-md">
            <h3 className="font-headline-section text-headline-section text-text-primary dark:text-white mb-4">Categories</h3>
            
            {/* Unified Table Container */}
            <div className="bg-white rounded-[24px] card-shadow flex flex-col overflow-hidden">
              <div className="px-6 py-5 bg-white border-b border-[#E8E8E8]">
                <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Budget Allocation</h3>
              </div>
              <div className="divide-y divide-[#E8E8E8]/50">
                {/* Row 1 */}
                <div className="px-6 py-4 hover:bg-[#F1F2F0]/30 transition-colors group">
                  <div className="flex justify-between items-center mb-3">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#6F6F6F] transition-all group-hover:bg-white group-hover:shadow-sm">
                        <span className="material-symbols-outlined icon-fill">restaurant</span>
                      </div>
                      <div>
                        <span className="text-sm font-semibold text-[#1a1c1b] block">Makanan</span>
                        <span className="text-xs text-[#6F6F6F] mt-0.5 block">Food & Dining</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[15px] font-bold text-[#1a1c1b]">Rp420.000 <span className="text-text-muted font-normal text-xs">/ Rp600.000</span></div>
                      <p className="text-[11px] font-semibold text-danger-red mt-1">70% Used</p>
                    </div>
                  </div>
                  <div className="w-full h-2 bg-[#F1F2F0] rounded-full overflow-hidden">
                    <div className="h-full bg-danger-red rounded-full" style={{ width: '70%' }}></div>
                  </div>
                </div>
                
                {/* Row 2 */}
                <div className="px-6 py-4 hover:bg-[#F1F2F0]/30 transition-colors group">
                  <div className="flex justify-between items-center mb-3">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#6F6F6F] transition-all group-hover:bg-white group-hover:shadow-sm">
                        <span className="material-symbols-outlined icon-fill">directions_car</span>
                      </div>
                      <div>
                        <span className="text-sm font-semibold text-[#1a1c1b] block">Transportasi</span>
                        <span className="text-xs text-[#6F6F6F] mt-0.5 block">Transportation</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[15px] font-bold text-[#1a1c1b]">Rp150.000 <span className="text-text-muted font-normal text-xs">/ Rp500.000</span></div>
                      <p className="text-[11px] font-semibold text-[#6F6F6F] mt-1">30% Used</p>
                    </div>
                  </div>
                  <div className="w-full h-2 bg-[#F1F2F0] rounded-full overflow-hidden">
                    <div className="h-full bg-[#c7ff00] rounded-full" style={{ width: '30%' }}></div>
                  </div>
                </div>
                
                {/* Row 3 */}
                <div className="px-6 py-4 hover:bg-[#F1F2F0]/30 transition-colors group">
                  <div className="flex justify-between items-center mb-3">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#6F6F6F] transition-all group-hover:bg-white group-hover:shadow-sm">
                        <span className="material-symbols-outlined icon-fill">receipt</span>
                      </div>
                      <div>
                        <span className="text-sm font-semibold text-[#1a1c1b] block">Tagihan</span>
                        <span className="text-xs text-[#6F6F6F] mt-0.5 block">Bills & Utilities</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[15px] font-bold text-[#1a1c1b]">Rp800.000 <span className="text-text-muted font-normal text-xs">/ Rp1.000.000</span></div>
                      <p className="text-[11px] font-semibold text-warning-amber mt-1">80% Used</p>
                    </div>
                  </div>
                  <div className="w-full h-2 bg-[#F1F2F0] rounded-full overflow-hidden">
                    <div className="h-full bg-warning-amber rounded-full" style={{ width: '80%' }}></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          {/* Insights & Right Col */}
          <div className="space-y-stack-md">
            <h3 className="font-headline-section text-headline-section text-text-primary dark:text-white mb-4 opacity-0 hidden lg:block">Insights</h3>
            
            {/* Insight Card */}
            <div className="bg-surface-muted dark:bg-inverse-surface rounded-[24px] p-6">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-full bg-surface-white dark:bg-black flex flex-shrink-0 items-center justify-center text-primary-container shadow-sm">
                  <span className="material-symbols-outlined">lightbulb</span>
                </div>
                <div>
                  <h4 className="font-title-card text-title-card text-text-primary dark:text-white mb-2">Budget Insights</h4>
                  <p className="font-body-main text-body-main text-text-muted leading-relaxed">
                    Your <strong>Makanan</strong> budget is 70% used. Consider slowing down on dining out for the rest of the week to stay on track.
                  </p>
                </div>
              </div>
            </div>
            
            {/* Upcoming Bills */}
            <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-6 card-shadow">
              <h4 className="font-title-card text-title-card text-text-primary dark:text-white mb-4">Upcoming Bills</h4>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-[14px] bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center text-text-primary dark:text-white">
                      <span className="material-symbols-outlined">wifi</span>
                    </div>
                    <div>
                      <div className="font-body-strong text-body-strong text-text-primary dark:text-white">Internet</div>
                      <div className="font-label-muted text-label-muted text-text-muted">In 3 days</div>
                    </div>
                  </div>
                  <div className="font-body-strong text-body-strong text-text-primary dark:text-white">Rp350.000</div>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-[14px] bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center text-text-primary dark:text-white">
                      <span className="material-symbols-outlined">flash_on</span>
                    </div>
                    <div>
                      <div className="font-body-strong text-body-strong text-text-primary dark:text-white">Listrik</div>
                      <div className="font-label-muted text-label-muted text-text-muted">In 5 days</div>
                    </div>
                  </div>
                  <div className="font-body-strong text-body-strong text-text-primary dark:text-white">Rp400.000</div>
                </div>
              </div>
              <button className="w-full mt-6 py-3 border border-border-light dark:border-[#333] rounded-full font-label-button text-label-button text-text-primary dark:text-white hover:bg-surface-muted dark:hover:bg-[#2A2A2A] transition-colors">
                View All Bills
              </button>
            </div>
          </div>
        </div>
      </div>
      
      {/* =======================
          MOBILE VIEW (md:hidden)
          ======================= */}
      <div className="md:hidden space-y-stack-lg relative w-full pt-4 pb-20">
        <div className="ambient-glow"></div>
        
        {/* Header: Total Remaining */}
        <section className="text-center space-y-stack-sm relative z-10">
          <p className="font-label-muted text-label-muted text-text-muted">Total Remaining Budget</p>
          <h2 className="font-headline-hero text-3xl font-bold text-text-primary dark:text-white tracking-tight">Rp1.250.000</h2>
          <div className="flex justify-center pt-4">
            <button className="h-14 bg-primary-container rounded-full flex items-center justify-center text-text-primary shadow-lg hover:scale-105 active:scale-95 transition-transform px-8">
              <span className="material-symbols-outlined text-[28px]">add</span>
            </button>
          </div>
        </section>
        
        {/* Quick Stats Grid */}
        <section className="grid grid-cols-2 gap-stack-md">
          <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow flex flex-col justify-between h-[100px]">
            <div className="flex items-center gap-2 text-text-muted">
              <div className="w-6 h-6 rounded-full bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center">
                <span className="material-symbols-outlined text-[14px]">account_balance</span>
              </div>
              <span className="font-label-muted text-label-muted">Budget</span>
            </div>
            <p className="font-title-card text-title-card text-text-primary dark:text-white">Rp4.000.000</p>
          </div>
          
          <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow flex flex-col justify-between h-[100px]">
            <div className="flex items-center gap-2 text-text-muted">
              <div className="w-6 h-6 rounded-full bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center">
                <span className="material-symbols-outlined text-[14px]">shopping_cart</span>
              </div>
              <span className="font-label-muted text-label-muted">Spent</span>
            </div>
            <p className="font-title-card text-title-card text-text-primary dark:text-white">Rp2.750.000</p>
          </div>
        </section>
        
        {/* Budget Category List */}
        <section className="space-y-stack-md">
          <div className="flex items-center justify-between pb-2">
            <h3 className="font-headline-section text-headline-section text-text-primary dark:text-white">Categories</h3>
            <span className="font-label-button text-label-button text-primary dark:text-primary-container">See All</span>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            {/* Card 1 */}
            <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow hover-lift flex flex-col justify-between">
              <div className="flex flex-col gap-2 mb-4">
                <div className="w-10 h-10 rounded-full bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center text-text-primary dark:text-white">
                  <span className="material-symbols-outlined icon-fill">restaurant</span>
                </div>
                <div>
                  <h4 className="font-title-card text-title-card text-text-primary dark:text-white truncate">Makanan</h4>
                  <p className="font-label-muted text-label-muted text-text-muted">40% left</p>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-end">
                  <p className="font-title-card text-title-card text-text-primary dark:text-white">Rp600k</p>
                  <p className="font-label-muted text-label-muted text-text-muted text-[10px]">/ 1.5M</p>
                </div>
                <div className="w-full h-2 bg-surface-muted dark:bg-[#2A2A2A] rounded-full overflow-hidden">
                  <div className="h-full bg-primary-container rounded-full" style={{ width: '60%' }}></div>
                </div>
              </div>
            </div>
            
            {/* Card 2 */}
            <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow hover-lift flex flex-col justify-between">
              <div className="flex flex-col gap-2 mb-4">
                <div className="w-10 h-10 rounded-full bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center text-text-primary dark:text-white">
                  <span className="material-symbols-outlined icon-fill">directions_car</span>
                </div>
                <div>
                  <h4 className="font-title-card text-title-card text-text-primary dark:text-white truncate">Transportasi</h4>
                  <p className="font-label-muted text-label-muted text-text-muted">20% left</p>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-end">
                  <p className="font-title-card text-title-card text-text-primary dark:text-white">Rp200k</p>
                  <p className="font-label-muted text-label-muted text-text-muted text-[10px]">/ 1M</p>
                </div>
                <div className="w-full h-2 bg-surface-muted dark:bg-[#2A2A2A] rounded-full overflow-hidden">
                  <div className="h-full bg-primary-container rounded-full" style={{ width: '80%' }}></div>
                </div>
              </div>
            </div>
            
            {/* Card 3 */}
            <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow hover-lift flex flex-col justify-between">
              <div className="flex flex-col gap-2 mb-4">
                <div className="w-10 h-10 rounded-full bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center text-text-primary dark:text-white">
                  <span className="material-symbols-outlined icon-fill">shopping_bag</span>
                </div>
                <div>
                  <h4 className="font-title-card text-title-card text-text-primary dark:text-white truncate">Belanja</h4>
                  <p className="font-label-muted text-label-muted text-text-muted">60% left</p>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-end">
                  <p className="font-title-card text-title-card text-text-primary dark:text-white">Rp300k</p>
                  <p className="font-label-muted text-label-muted text-text-muted text-[10px]">/ 500k</p>
                </div>
                <div className="w-full h-2 bg-surface-muted dark:bg-[#2A2A2A] rounded-full overflow-hidden">
                  <div className="h-full bg-primary-container rounded-full" style={{ width: '40%' }}></div>
                </div>
              </div>
            </div>
            
            {/* Card 4 */}
            <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow hover-lift flex flex-col justify-between">
              <div className="flex flex-col gap-2 mb-4">
                <div className="w-10 h-10 rounded-full bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center text-text-primary dark:text-white">
                  <span className="material-symbols-outlined icon-fill">movie</span>
                </div>
                <div>
                  <h4 className="font-title-card text-title-card text-text-primary dark:text-white truncate">Hiburan</h4>
                  <p className="font-label-muted text-label-muted text-danger-red">15% left</p>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-end">
                  <p className="font-title-card text-title-card text-danger-red">Rp150k</p>
                  <p className="font-label-muted text-label-muted text-text-muted text-[10px]">/ 1M</p>
                </div>
                <div className="w-full h-2 bg-surface-muted dark:bg-[#2A2A2A] rounded-full overflow-hidden">
                  <div className="h-full bg-danger-red rounded-full" style={{ width: '85%' }}></div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
